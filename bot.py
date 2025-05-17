import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from io import BytesIO
from openai import AsyncOpenAI, OpenAIError
import logging
import re
from collections import defaultdict
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")

if not DISCORD_TOKEN or not GROK_API_KEY:
    raise ValueError("Missing required environment variables: DISCORD_TOKEN or GROK_API_KEY")

# Initialize AsyncOpenAI client
client = AsyncOpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")

# Constants
MODEL = "grok-3-beta"
MAX_TOKENS = 128000
MAX_RESPONSE_TOKENS = 400
DISCORD_MAX_CHARS = 1800  # safe limit below Discord's 2000 char limit
MAX_HISTORY_CHARS = 100000  # rough limit for history truncation

# Discord intents and bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# State tracking
conversation_history = defaultdict(list)  # key: userID_channelID, value: list of messages

# Utility functions

def is_image_generation_request(content: str) -> bool:
    """Detect if user is requesting image generation."""
    return bool(re.search(r'\b(generate|create|make|draw)\b.*\b(image|picture|art|photo)\b', content, re.IGNORECASE))

def is_simple_question(content: str) -> bool:
    """Detect if question is simple based on keywords or length."""
    content = content.lower().strip()
    if len(content.split()) < 10:
        return True
    simple_keywords = ['what is', 'who is', 'when is', 'where is', 'how many', 'define']
    return any(content.startswith(keyword) for keyword in simple_keywords)

def truncate_history(messages: list, max_chars: int) -> list:
    """Truncate conversation history to fit within max_chars."""
    total_chars = 0
    truncated = []
    for msg in reversed(messages):
        msg_chars = len(msg["content"])
        if total_chars + msg_chars <= max_chars:
            truncated.insert(0, msg)
            total_chars += msg_chars
        else:
            break
    return truncated

def build_system_prompt(is_simple: bool) -> tuple:
    """Return system prompt and max tokens based on question complexity."""
    if is_simple:
        prompt = (
            "Answer directly and concisely in plain language. "
            "Keep your answer under 350 characters and 2-3 sentences. "
            "Do not over-explain or elaborate. Only state the essential facts."
        )
        max_tokens = 100
    else:
        prompt = (
            "Answer clearly and concisely. "
            "Keep your answer under 1800 characters, focusing on main points. "
            "Avoid unnecessary detail or repetition."
        )
        max_tokens = MAX_RESPONSE_TOKENS
    return {"role": "system", "content": prompt}, max_tokens

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes, limiting to first 5 pages."""
    reader = PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages[:5]:  # Limit to 5 pages for performance
        extracted = page.extract_text()
        if extracted:
            text += extracted
    if not text:
        raise ValueError("No text could be extracted from the PDF")
    return text

def truncate_text(text: str, max_chars: int) -> str:
    """Simple truncation to max_chars."""
    return text[:max_chars]

async def query_grok(messages: list, is_simple: bool) -> str:
    """Asynchronous Grok API call."""
    try:
        system_prompt, max_tokens = build_system_prompt(is_simple)
        full_messages = [system_prompt] + messages
        response = await client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            temperature=0.7,
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        raise

async def generate_image(prompt: str) -> str:
    """Generate image URL via Grok API."""
    try:
        response = await client.images.generate(
            model="flux.1",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        return response.data[0].url
    except OpenAIError as e:
        logger.error(f"Image generation error: {str(e)}")
        raise

# Discord event handlers

@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")

@bot.command(name="help")
async def help_command(ctx):
    help_text = (
        "**Grok Bot Help**\n"
        "How to use the bot:\n"
        "- **Mention or Reply**: Mention the bot (`@GrokBot`) or reply to its message to ask a question.\n"
        "- **Image Generation**: Use phrases like 'generate an image of...' to create images.\n"
        "- **PDF Support**: Attach a PDF to extract and query its text.\n"
        "- **Commands**: `!help` - Show this help message"
    )
    await ctx.send(help_text)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip()
    is_reply_to_bot = False
    history_key = f"{message.author.id}_{message.channel.id}"

    # Check if message is reply to bot
    if message.reference and message.reference.resolved:
        if message.reference.resolved.author == bot.user:
            is_reply_to_bot = True

    # Handle PDF or image attachments
    for attachment in message.attachments:
        if attachment.filename.endswith(".pdf"):
            try:
                file_bytes = await attachment.read()
                content = extract_text_from_pdf(file_bytes)
                content = truncate_text(content, max_chars=3000)
                break
            except Exception as e:
                logger.error(f"PDF processing error: {str(e)}")
                await message.reply(f"[PDF Error] Failed to process PDF: {str(e)}", mention_author=False)
                return
        elif attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
            content = f"Image uploaded: {attachment.filename} (image analysis not supported, try generating an image instead)"
            break

    # Process if mention or reply
    if message.content.startswith(f"<@{bot.user.id}>") or is_reply_to_bot:
        if message.content.startswith(f"<@{bot.user.id}>"):
            content = message.content.replace(f"<@{bot.user.id}>", "").strip()

        if content:
            # Image generation path
            if is_image_generation_request(content):
                async with message.channel.typing():
                    try:
                        image_url = await generate_image(content)
                        await message.reply(f"Generated image: {image_url}", mention_author=False)
                        conversation_history[history_key].append({"role": "user", "content": content})
                        conversation_history[history_key].append({"role": "assistant", "content": f"Generated image: {image_url}"})
                    except OpenAIError as e:
                        await message.reply(f"[Image Generation Error] {str(e)}", mention_author=False)
                return

            # Add user message to history and truncate
            conversation_history[history_key].append({"role": "user", "content": content})
            total_chars = sum(len(msg["content"]) for msg in conversation_history[history_key])
            if total_chars > MAX_HISTORY_CHARS:
                conversation_history[history_key][:] = truncate_history(conversation_history[history_key], MAX_HISTORY_CHARS)

            async with message.channel.typing():
                try:
                    response_text = await query_grok(
                        conversation_history[history_key],
                        is_simple_question(content)
                    )
                    conversation_history[history_key].append({"role": "assistant", "content": response_text})

                    await message.reply(response_text, mention_author=False)

                except OpenAIError as e:
                    logger.error(f"Grok API error: {str(e)}")
                    await message.reply(f"[Grok API Error] {str(e)}", mention_author=False)
                except Exception as e:
                    logger.error(f"Unexpected error: {str(e)}")
                    await message.reply(f"[Unexpected Error] {str(e)}", mention_author=False)

    await bot.process_commands(message)

# Run the bot
bot.run(DISCORD_TOKEN)
