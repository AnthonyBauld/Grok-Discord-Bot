import discord
import requests
import json
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Grok API endpoint
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# Discord client setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# In-memory conversation tracking
user_context = {}

async def send_to_grok(user_id, message):
    messages = user_context.get(user_id, [])
    messages.append({"role": "user", "content": message})

    payload = {
        "model": "grok-3-latest",
        "messages": messages,
        "stream": False,
        "temperature": 0.5
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROK_API_KEY}"
    }

    try:
        response = requests.post(GROK_API_URL, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": reply})
            user_context[user_id] = messages[-10:]  # Limit history
            return reply
        else:
            return f"[Grok API Error] {response.status_code}: {response.json()}"
    except Exception as e:
        return f"[Request Failed] {str(e)}"

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if client.user in message.mentions:
        content = message.content.replace(f"<@{client.user.id}>", "").strip()
        if not content:
            await message.channel.send("❓ Please mention me with a question.")
            return

        await message.channel.typing()
        reply = await send_to_grok(str(message.author.id), content)
        await message.channel.send(reply[:2000])

client.run(DISCORD_TOKEN)
