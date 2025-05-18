# Grok 3.0 Discord Bot

This Discord bot uses Grok's 3.0 model to answer user prompts when the bot is mentioned in chat. It supports conversational memory, PDF reading, and can be extended to handle images and videos.

---

## 🧱 Requirements

- Python 3.9+
- A Discord bot token (from [Discord Developer Portal](https://discord.com/developers/applications))
- A Grok API key (from [xAI Developer Console](https://docs.x.ai/docs/overview))
- `pip` (Python package installer)
  
---

## ⚙️ Setup Instructions

1. Create a `.env` file in the same directory with the following content:

    ```
    DISCORD_TOKEN=your-discord-token-here
    GROK_API_KEY=your-grok-api-key-here
    ```

2. Install dependencies:

    ```
    pip install discord.py requests python-dotenv
    ```

    *Optional:* Save dependencies to `requirements.txt`:

    ```
    pip freeze > requirements.txt
    ```

3. Run the bot:

    ```
    python bot.py
    ```

---

## 💡 Usage

Mention the bot in any server where it has permission. Example:


The bot will:

- Respond using Grok 3.0
- Retain short conversation history
- Read and respond to PDF content in the same message
- (Optionally) support images and videos if extended

---

## 🧠 Features

- ✅ Grok 3.0 API support via `xAI Developer Console`
- ✅ Remembers recent conversation context (user-specific or global)
- ✅ Supports PDF document upload and answering within one message
- ✅ Environment-based secrets using `.env`
- ✅ Outputs concise but informative answers
- ✅ Gracefully handles quota, length, and format errors

---

## ⚠️ Troubleshooting

| Error                      | Solution                                           |
|----------------------------|---------------------------------------------------|
| API quota exceeded          | You’ve hit your Grok limit. Check xAI Console |
| content must be 2000 or fewer in length | Message too long. Grok limits apply. Keep user prompts short. |
| ModuleNotFoundError        | Run pip install commands again or check your Python environment |
| Bot doesn’t reply          | Ensure MESSAGE CONTENT INTENT is enabled in Discord Dev Portal |

---

## 🚀 Extensions (Ideas)

- Handle image and video files using Grok's multimodal support
- Add slash command support (`/ask`)
- Use persistent file-backed memory (SQLite or JSON store)
- Add rate limiting or moderation filters

---

## 🔐 Notes

Keep your `.env` file secret. Never upload it to GitHub or any public space.

