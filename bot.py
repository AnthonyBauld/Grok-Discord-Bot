import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from io import BytesIO
from openai import OpenAI, OpenAIError
import tiktoken
import logging
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import re
from discord import File

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Validate environment variables
if not DISCORD_TOKEN or not GROK_API_KEY:
    raise ValueError("Missing required environment variables: DISCORD_TOKEN or GROK_API_KEY")

# Initialize OpenAI client for xAI API
client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")

MODEL = "grok-3-beta"
MAX_TOKENS = 128000
MAX_RESPONSE_TOKENS = 400  # ~500 words (0.75 tokens/word)
RATE_LIMIT = 5  # Max 5 requests per minute per user
COOLDOWN_SECONDS = 60 / RATE_LIMIT
DISCORD_MAX_CHARS = 1800  # Target slightly below Discord's 2000-char limit

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)  # Disable default help command

# Note: PyNaCl is not installed, so voice features are disabled. Install with `pip install PyNaCl` if needed.

# Store conversation history per user/channel
conversation_history = defaultdict(list)
# Track user request timestamps for rate limiting
user_requests = defaultdict(list)

def is_image_generation_request(content):
    """Check if the message is requesting image generation."""
    return bool(re.search(r'\b(generate|create|make|draw)\b.*\b(image|picture|art|photo)\b', content, re.IGNORECASE))

def is_simple_question(content):
    """Determine if the question is simple based on length or keywords."""
    content = content.lower().strip()
    # Short questions (< 10 words) or common factual queries
    if len(content.split()) < 10:
        return True
    # Keywords for simple factual questions
    simple_keywords = ['what is', 'who is', 'when is', 'where is', 'how many', 'define']
    return any(content.startswith(keyword) for keyword in simple_keywords)

async def generate_image(prompt):
    """Generate an image using FLUX.1 via Grok API."""
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

def truncate_to_char_limit(text, max_chars):
    """Truncate or summarize text to fit within Discord's character limit, preserving coherence."""
    if len(text) <= max_chars:
        return text
    # Find the last period or space before the limit
    cutoff = text[:max_chars].rfind('.')
    if cutoff == -1:
        cutoff = text[:max_chars].rfind(' ')
    if cutoff == -1:
        cutoff = max_chars - 100  # Reserve space for summary
    summary = "... (response shortened due to Discord's 2000-character limit; key points summarized)"
    return text[:cutoff] + summary

@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")

@bot.command(name="help")
async def help_command(ctx):
    """Provide help information for the bot."""
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

    # Rate limiting
    now = datetime.utcnow()
    user_id = message.author.id
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < timedelta(seconds=60)]
    if len(user_requests[user_id]) >= RATE_LIMIT:
        await message.reply("You're sending requests too quickly! Please wait a moment.", mention_author=False)
        return
    user_requests[user_id].append(now)

    content = None
    is_reply_to_bot = False
    history_key = f"{message.author.id}_{message.channel.id}"

    # Check if the message is a reply to the bot
    if message.reference and message.reference.resolved:
        referenced_message = message.reference.resolved
        if referenced_message.author == bot.user:
            is_reply_to_bot = True
            content = message.content.strip()

    # Handle PDF attachments
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

    # Handle image attachments (not supported for processing)
    for attachment in message.attachments:
        if attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
            content = f"Image uploaded: {attachment.filename} (image analysis not supported, try generating an image instead)"
            break

    # Process text input if it's a mention or a reply to the bot
    if message.content.startswith(f"<@{bot.user.id}>") or is_reply_to_bot:
        if message.content.startswith(f"<@{bot.user.id}>"):
            query = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if not content:
                content = query

        if not content:
            content = message.content.strip()

        if content:
            async with message.channel.typing():
                # Check for image generation request
                if is_image_generation_request(content):
                    try:
                        image_url = await generate_image(content)
                        await message.reply(f"Generated image: {image_url}", mention_author=False)
                        conversation_history[history_key].append({"role": "user", "content": content})
                        conversation_history[history_key].append({"role": "assistant", "content": f"Generated image: {image_url}"})
                    except OpenAIError as e:
                        await message.reply(f"[Image Generation Error] {str(e)}", mention_author=False)
                    return

                # Add user message to history
                conversation_history[history_key].append({"role": "user", "content": content})
                conversation_history[history_key][:] = truncate_history(conversation_history[history_key], MAX_TOKENS - MAX_RESPONSE_TOKENS - 50)  # Reserve tokens for system prompt

                try:
                    response_text = await query_grok(conversation_history[history_key], is_simple_question(content))
                    conversation_history[history_key].append({"role": "assistant", "content": response_text})
                    # Truncate to Discord's character limit if necessary
                    response_text = truncate_to_char_limit(response_text, DISCORD_MAX_CHARS)
                    await message.reply(response_text, mention_author=False)
                except OpenAIError as e:
                    logger.error(f"Grok API error: {str(e)}")
                    await message.reply(f"[Grok API Error] {str(e)}", mention_author=False)
                except Exception as e:
                    logger.error(f"Unexpected error: {str(e)}")
                    await message.reply(f"[Unexpected Error] {str(e)}", mention_author=False)

    await bot.process_commands(message)

async def query_grok(messages, is_simple):
    try:
        # Choose system prompt based on question complexity
        if is_simple:
            system_prompt = {
                "role": "system",
                "content": "Provide a brief, accurate answer in under 100 words and 500 characters, focusing on key facts without elaboration."
            }
            max_tokens = min(MAX_RESPONSE_TOKENS, 100)  # Limit tokens for simple questions
        else:
            system_prompt = {
                "role": "system",
                "content": "Provide a complete and accurate answer in under 500 words and 1800 characters, prioritizing brevity while fully addressing the query. Avoid unnecessary elaboration."
            }
            max_tokens = MAX_RESPONSE_TOKENS

        full_messages = [system_prompt] + messages
        response = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            temperature=0.7,
            max_tokens=max_tokens,
            stream=False
        )
        response_text = response.choices[0].message.content.strip()
        # Retry if response exceeds character limit
        if len(response_text) > DISCORD_MAX_CHARS:
            system_prompt["content"] = system_prompt["content"].replace("1800 characters", "1500 characters").replace("500 characters", "400 characters").replace("500 words", "400 words").replace("100 words", "80 words")
            full_messages = [system_prompt] + messages
            response = client.chat.completions.create(
                model=MODEL,
                messages=full_messages,
                temperature=0.7,
                max_tokens=max_tokens - 100,  # Reduce tokens for retry
                stream=False
            )
            response_text = response.choices[0].message.content.strip()
        return response_text
    except OpenAIError as e:
        raise

def extract_text_from_pdf(file_bytes):
    reader = PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    if not text:
        raise ValueError("No text could be extracted from the PDF")
    return text

def truncate_text(text, max_chars):
    """Truncate text to a maximum character length."""
    return text[:max_chars] if len(text) > max_chars else text

def truncate_history(messages, max_tokens):
    """Truncate conversation history to stay within token limits."""
    encoding = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    truncated_messages = []
    
    for msg in reversed(messages):
        msg_tokens = len(encoding.encode(msg["content"]))
        if total_tokens + msg_tokens <= max_tokens:
            truncated_messages.insert(0, msg)
            total_tokens += msg_tokens
        else:
            break
    return truncated_messages

# Run the bot
bot.run(DISCORD_TOKEN)
