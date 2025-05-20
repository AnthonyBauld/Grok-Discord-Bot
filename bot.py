# -*- coding: utf-8 -*-
# Import required libraries for the Discord bot
import os                  # For accessing environment variables
import discord            # Discord API library for bot functionality
from dotenv import load_dotenv  # To load environment variables from .env
from PyPDF2 import PdfReader    # For extracting text from PDF files
from io import BytesIO         # For handling PDF file bytes
from openai import AsyncOpenAI, OpenAIError  # For async Grok API calls
import logging            # For logging errors to console
import re                 # For regex pattern matching
from collections import defaultdict  # For tracking conversation history

# Configure logging for error tracking
logging.basicConfig(
    level=logging.ERROR,  # Log only errors for minimal output
    format='%(asctime)s - %(levelname)s - %(message)s'  # Include timestamp
)
logger = logging.getLogger(__name__)  # Create logger instance

# Load environment variables from .env file
load_dotenv()

# Bot configuration using environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # Discord bot token
GROK_API_KEY = os.getenv("GROK_API_KEY")   # Grok API key for xAI

# Validate environment variables
if not DISCORD_TOKEN or not GROK_API_KEY:
    raise ValueError("Missing required environment variables")

# Initialize AsyncOpenAI client for Grok API
client = AsyncOpenAI(
    api_key=GROK_API_KEY,  # Use Grok API key
    base_url="https://api.x.ai/v1"  # xAI API endpoint
)

# Define constants for bot configuration
MODEL = "grok-3-beta"            # Grok model for text responses
MAX_RESPONSE_TOKENS = 400        # Max tokens for Grok responses
DISCORD_MAX_CHARS = 1800         # Max characters for Discord messages
MAX_HISTORY_CHARS = 100000       # Max characters for conversation history

# Set up Discord client with required intents
intents = discord.Intents.default()  # Use default intents
intents.messages = True             # Enable message events
intents.message_content = True      # Enable message content access
bot = discord.Client(intents=intents)  # Create Discord client

# Track conversation history per user and channel
conversation_history = defaultdict(list)  # Store messages by user_channel key

# Utility function: Detect image generation requests
def is_image_generation_request(content: str) -> bool:
    """Check if the message is an image generation request."""
    # Use regex to match 'generate/create/draw' + 'image/picture/art'
    return bool(re.search(r'^(generate|create|draw)\s+.*\b(image|picture|art)\b', content, re.IGNORECASE))

# Utility function: Detect simple questions
def is_simple_question(content: str) -> bool:
    """Identify short or simple questions for brief responses."""
    content = content.lower().strip()

    # Consider very short messages (< 8 words) as simple
    if len(content.split()) < 8:
        return True

    # Check for simple question starters and common short phrases
    simple_keywords = [
        'what is', 'who is', 'when is', 'where is', 'how many', 'define',
        'explain', 'tell me about', 'what are', 'can you tell me', 'is it',
        'what\'s', 'who\'s', 'why is', 'how does', 'what\'s the'
    ]
    if any(content.startswith(keyword) for keyword in simple_keywords):
        return True

    # Check for questions that are very short and end with a question mark
    if len(content.split()) <= 5 and content.endswith('?'):
        return True

    return False

# Utility function: Truncate conversation history
def truncate_history(messages: list, max_chars: int) -> list:
    """Limit conversation history to max_chars to avoid overflow."""
    total_chars = 0
    truncated = []
    # Iterate backwards to keep recent messages
    for msg in messages[::-1]:
        msg_chars = len(msg["content"])
        if total_chars + msg_chars <= max_chars:
            truncated.append(msg)
            total_chars += msg_chars
        else:
            break
    return truncated[::-1]  # Reverse back to original order

# Utility function: Build system prompt
def build_system_prompt(is_simple: bool) -> tuple:
    """Create system prompt and max tokens based on question type."""
    if is_simple:
        # Short prompt for simple questions, emphasizing extreme brevity
        prompt = "Provide a very brief, direct answer (1-2 sentences, max 200 characters). Use plain language."
        max_tokens = 70 # Reduced tokens to enforce brevity
    else:
        # Default prompt for detailed responses
        prompt = "Answer concisely, under 1800 chars. Focus on main points."
        max_tokens = MAX_RESPONSE_TOKENS
    return {"role": "system", "content": prompt}, max_tokens

# Utility function: Extract text from PDF
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF, limit to 3000 chars."""
    reader = PdfReader(BytesIO(file_bytes))  # Read PDF from bytes
    text = ""
    # Process up to 5 pages
    for page in reader.pages[:5]:
        if len(text) >= 3000:
            break
        extracted = page.extract_text()
        if extracted:
            text += extracted
    if not text:
        raise ValueError("No text extracted from PDF")
    return text[:3000]  # Cap at 3000 chars

# Async function: Query Grok API for text responses
async def query_grok(messages: list, is_simple: bool) -> str:
    """Send messages to Grok API and return response."""
    try:
        system_prompt, max_tokens = build_system_prompt(is_simple)
        # Make async API call to Grok
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[system_prompt] + messages,
            temperature=0.7,  # Moderate creativity
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        logger.error(f"Grok API error: {str(e)}")
        raise

# Discord event: Handle bot startup
@bot.event
async def on_ready():
    """Run when bot connects to Discord."""
    # Log successful login
    logger.error(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    # Set custom activity status
    await bot.change_presence(activity=discord.CustomActivity(name="Change Me"))

# Discord event: Handle incoming messages
@bot.event
async def on_message(message):
    """Process messages, respond to mentions, replies, or PDF attachments."""
    if message.author == bot.user:
        return  # Ignore bot's own messages

    content = message.content.strip()
    # Create unique key for conversation history
    history_key = f"{message.author.id}_{message.channel.id}"
    should_process = False

    # Check for bot mention
    if message.content.startswith(f"<@{bot.user.id}>"):
        content = content.replace(f"<@{bot.user.id}>", "").strip()
        should_process = True
    # Check for reply to bot
    elif message.reference and message.reference.resolved and message.reference.resolved.author == bot.user:
        should_process = True

    # Handle file attachments only if bot is mentioned or replied to
    if should_process:
        for attachment in message.attachments:
            if attachment.filename.endswith(".pdf"):
                try:
                    # Read PDF bytes
                    file_bytes = await attachment.read()
                    content = extract_text_from_pdf(file_bytes)
                    break  # Process PDF and proceed to response
                except Exception as e:
                    logger.error(f"PDF error: {str(e)}")
                    await message.reply(f"[PDF Error] {str(e)}", mention_author=False)
                    return
            elif attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                # Respond only for direct image uploads
                await message.reply("Image handling is not supported.", mention_author=False)
                return  # Stop further processing

    # Process valid text or PDF-based messages
    if should_process and content:
        async with message.channel.typing():
            if is_image_generation_request(content):
                # Reply that image generation is not supported
                await message.reply("Image generation is not supported.", mention_author=False)
                # Update conversation history
                conversation_history[history_key].extend([
                    {"role": "user", "content": content},
                    {"role": "assistant", "content": "Image generation is not supported."}
                ])
            else:
                # Add user message to history
                conversation_history[history_key].append({"role": "user", "content": content})
                # Truncate history if too long
                if sum(len(msg["content"]) for msg in conversation_history[history_key]) > MAX_HISTORY_CHARS:
                    conversation_history[history_key][:] = truncate_history(conversation_history[history_key], MAX_HISTORY_CHARS)

                try:
                    # Query Grok for response
                    response = await query_grok(conversation_history[history_key], is_simple_question(content))
                    # Update history with response
                    conversation_history[history_key].append({"role": "assistant", "content": response})
                    # Send response, capped at Discord limit
                    await message.reply(response[:DISCORD_MAX_CHARS], mention_author=False)
                except OpenAIError as e:
                    await message.reply(f"[Grok Error] {str(e)}", mention_author=False)
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    await message.reply(f"[Error] {str(e)}", mention_author=False)

# Run the bot with Discord token
bot.run(DISCORD_TOKEN)
