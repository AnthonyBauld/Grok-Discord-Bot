# -*- coding: utf-8 -*-
import os
import discord
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from io import BytesIO
from openai import AsyncOpenAI, OpenAIError
import logging
import re
from collections import defaultdict

# Setup logging (minimal for speed)
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")

if not DISCORD_TOKEN or not GROK_API_KEY:
    raise ValueError("Missing required environment variables")

# Initialize AsyncOpenAI client
client = AsyncOpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")

# Constants
MODEL = "grok-3-beta"
MAX_RESPONSE_TOKENS = 400
DISCORD_MAX_CHARS = 1800
MAX_HISTORY_CHARS = 100000

# Discord client setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = discord.Client(intents=intents)

# State tracking
conversation_history = defaultdict(list)

# Utility functions
def is_image_generation_request(content: str) -> bool:
    """Detect image generation requests (simplified regex)."""
    return bool(re.search(r'^(generate|create|draw)\s+.*\b(image|picture|art)\b', content, re.IGNORECASE))

def is_simple_question(content: str) -> bool:
    """Detect simple questions for shorter responses."""
    content = content.lower().strip()
    if len(content.split()) < 10:
        return True
    simple_keywords = ['what is', 'who is', 'when is', 'where is', 'how many', 'define']
    return any(content.startswith(keyword) for keyword in simple_keywords)

def truncate_history(messages: list, max_chars: int) -> list:
    """Truncate history to fit max_chars (optimized)."""
    total_chars = 0
    truncated = []
    for msg in messages[::-1]:
        msg_chars = len(msg["content"])
        if total_chars + msg_chars <= max_chars:
            truncated.append(msg)
            total_chars += msg_chars
        else:
            break
    return truncated[::-1]

def build_system_prompt(is_simple: bool) -> tuple:
    """Return system prompt and max tokens."""
    if is_simple:
        prompt = "Answer in 2-3 sentences, under 350 chars. Be direct, use plain language."
        max_tokens = 100
    else:
        prompt = "Answer concisely, under 1800 chars. Focus on main points."
        max_tokens = MAX_RESPONSE_TOKENS
    return {"role": "system", "content": prompt}, max_tokens

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF, limit to 3000 chars."""
    reader = PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages[:5]:
        if len(text) >= 3000:
            break
        extracted = page.extract_text()
        if extracted:
            text += extracted
    if not text:
        raise ValueError("No text extracted from PDF")
    return text[:3000]

async def query_grok(messages: list, is_simple: bool) -> str:
    """Async Grok API call."""
    try:
        system_prompt, max_tokens = build_system_prompt(is_simple)
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[system_prompt] + messages,
            temperature=0.7,
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        logger.error(f"Grok API error: {str(e)}")
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

# Discord event handlers (Change the activity name to any string you want.)
@bot.event
async def on_ready():
    logger.error(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.CustomActivity(name="Change Me"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip()
    history_key = f"{message.author.id}_{message.channel.id}"
    should_process = False

    # Check for mention or reply
    if message.content.startswith(f"<@{bot.user.id}>"):
        content = content.replace(f"<@{bot.user.id}>", "").strip()
        should_process = True
    elif message.reference and message.reference.resolved and message.reference.resolved.author == bot.user:
        should_process = True

    # Handle attachments
    for attachment in message.attachments:
        if attachment.filename.endswith(".pdf"):
            try:
                file_bytes = await attachment.read()
                content = extract_text_from_pdf(file_bytes)
                should_process = True
                break
            except Exception as e:
                logger.error(f"PDF error: {str(e)}")
                await message.reply(f"[PDF Error] {str(e)}", mention_author=False)
                return
        elif attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
            content = f"Image uploaded: {attachment.filename} (analysis not supported)"
            should_process = True
            break

    if should_process and content:
        async with message.channel.typing():
            if is_image_generation_request(content):
                try:
                    image_url = await generate_image(content)
                    await message.reply(f"Generated image: {image_url}", mention_author=False)
                    conversation_history[history_key].extend([
                        {"role": "user", "content": content},
                        {"role": "assistant", "content": f"Generated image: {image_url}"}
                    ])
                except OpenAIError as e:
                    await message.reply(f"[Image Error] {str(e)}", mention_author=False)
            else:
                conversation_history[history_key].append({"role": "user", "content": content})
                if sum(len(msg["content"]) for msg in conversation_history[history_key]) > MAX_HISTORY_CHARS:
                    conversation_history[history_key][:] = truncate_history(conversation_history[history_key], MAX_HISTORY_CHARS)

                try:
                    response = await query_grok(conversation_history[history_key], is_simple_question(content))
                    conversation_history[history_key].append({"role": "assistant", "content": response})
                    await message.reply(response[:DISCORD_MAX_CHARS], mention_author=False)
                except OpenAIError as e:
                    await message.reply(f"[Grok Error] {str(e)}", mention_author=False)
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    await message.reply(f"[Error] {str(e)}", mention_author=False)

# Run the bot
bot.run(DISCORD_TOKEN)
