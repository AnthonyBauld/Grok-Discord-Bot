import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from io import BytesIO
from openai import OpenAI, OpenAIError
import tiktoken
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
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

# Initialize OpenAI client
client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")

# Constants
MODEL = "grok-3-beta"
MAX_TOKENS = 128000
MAX_RESPONSE_TOKENS = 400
RATE_LIMIT = 5  # requests per minute per user
DISCORD_MAX_CHARS = 1800  # safe limit below Discord's 2000 char limit

# Discord intents and bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# State tracking
conversation_history = defaultdict(list)  # key: userID_channelID, value: list of messages
user_requests = defaultdict(list)         # key: userID, value: list of request timestamps

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

def truncate_to_char_limit(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, trying to cut at sentence or word boundary."""
    if len(text) <= max_chars:
        return text
    cutoff = text[:max_chars].rfind('.')
    if cutoff == -1:
        cutoff = text[:max_chars].rfind(' ')
    if cutoff == -1:
        cutoff = max_chars - 100
    summary = "... (response shortened to fit Discord's 2000-character limit)"
    return text[:cutoff] + summary

def truncate_history(messages: list, max_tokens: int) -> list:
    """Truncate conversation history to fit within max_tokens."""
    encoding = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    truncated = []
    for msg in reversed(messages):
        msg_tokens = len(encoding.encode(msg["content"]))
        if total_tokens + msg_tokens <= max_tokens:
            truncated.insert(0, msg)
            total_tokens += msg_tokens
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
    """Extract text from PDF bytes."""
    reader = PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    if not text:
        raise ValueError("No text could be extracted from the PDF")
    return text

def truncate_text(text: str, max_chars: int) -> str:
    """Simple truncation to max_chars."""
    return text[:max_chars] if len(text) > max_chars else text

def query_grok_sync(messages: list, is_simple: bool) -> str:
    """Synchronous Grok API call with retry for length."""
    try:
        system_prompt, max_tokens = build_system_prompt(is_simple)
        full_messages = [system_prompt] + messages
        response = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            temperature=0.7,
            max_tokens=max_tokens,
            stream=False
        )
        response_text = response.choices[0].message.content.strip()

        # Retry with stricter prompt if too long
        if len(response_text) > DISCORD_MAX_CHARS:
            system_prompt["content"] += " Make your answer even shorter and more direct."
            full_messages = [system_prompt] + messages
            response = client.chat.completions.create(
                model=MODEL,
                messages=full_messages,
                temperature=0.7,
                max_tokens=max_tokens // 2,
                stream=False
            )
            response_text = response.choices[0].message.content.strip()

        return response_text
    except OpenAIError as e:
        raise

async def generate_image(prompt: str) -> str:
    """Generate image URL via Grok API."""
    try:
        response = client.images.generate(
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
            now = datetime.utcnow()
            user_id = message.author.id
            # Clean up old requests for rate limiting
            user_requests[user_id] = [t for t in user_requests[user_id] if now - t < timedelta(seconds=60)]
            if len(user_requests[user_id]) >= RATE_LIMIT:
                return  # silently ignore excess requests
            user_requests[user_id].append(now)

            async with message.channel.typing():
                # Image generation path
                if is_image_generation_request(content):
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
                conversation_history[history_key][:] = truncate_history(conversation_history[history_key], MAX_TOKENS - MAX_RESPONSE_TOKENS - 50)

                try:
                    loop = asyncio.get_running_loop()
                    response_text = await loop.run_in_executor(
                        None,
                        query_grok_sync,
                        conversation_history[history_key],
                        is_simple_question(content)
                    )
                    conversation_history[history_key].append({"role": "assistant", "content": response_text})

                    # Clean and truncate response
                    response_text = re.sub(r'\(Character count: \d+\)', '', response_text).strip()
                    response_text = truncate_to_char_limit(response_text, DISCORD_MAX_CHARS)

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
