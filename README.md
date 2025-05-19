# Grok Discord Bot

This Discord bot uses the Grok API from xAI to provide conversational responses, generate images, and process PDF attachments. It responds to mentions or replies, handles uploaded PDFs by extracting text, and acknowledges image uploads. The bot maintains conversation history per user and channel and logs errors to the console without persistent storage.

## Features
- **Text Responses**: Answers questions or processes text input using the Grok API (`grok-3-beta`), with short responses for simple questions (e.g., “What is AI?”) and detailed answers for complex queries.
- **Image Generation**: Creates images via the Grok API (`flux.1`) for requests like “generate image of a cat” and returns a URL.
- **PDF Processing**: Extracts text from uploaded PDFs (up to 3000 characters, 5 pages) and uses it as message content for Grok responses.
- **Image Upload Handling**: Acknowledges uploaded images (`.jpg`, `.jpeg`, `.png`) with a placeholder response (analysis not supported).
- **Conversation History**: Tracks per-user, per-channel history, truncated at 100,000 characters to maintain context.
- **Console-Only Logging**: Logs errors (e.g., API failures, PDF issues) to the console using `logging.ERROR`, with no disk storage.
- **Custom Activity**: Displays a custom activity status (default: “Change Me”).
- **Server Terminology**: Uses “server” instead of “guild” in logs and documentation for clarity.

## Setup Instructions

### Prerequisites
- **Python 3.8+**: Ensure Python is installed (`python --version` or `python3 --version`).
- **Discord Bot Token**: Create a bot at [Discord Developer Portal](https://discord.com/developers/applications).
- **Grok API Key**: Obtain from xAI at [https://x.ai/api](https://x.ai/api).
- **GitHub Repository**: Clone or download this repository to your local machine.

### Steps
1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/grok-discord-bot.git
   cd grok-discord-bot
   ```

2. **Create and Configure `.env`**
   - Create a `.env` file in the project root.
   - Add your Discord bot token and Grok API key:
     ```env
     DISCORD_TOKEN=your_discord_bot_token
     GROK_API_KEY=your_grok_api_key
     ```
   - Replace `your_discord_bot_token` with your bot’s token from the Discord Developer Portal.
   - Replace `your_grok_api_key` with your API key from xAI.
   - Example `.env`:
     ```env
     DISCORD_TOKEN=MTAzMjE2NjE3NjEyMzQ1Njc4.YcZx9w.ABC123xyz
     GROK_API_KEY=your_grok_key
     ```
   - Save `.env` and keep it secure (excluded by `.gitignore`).

3. **Install Dependencies**
   ```bash
   pip install discord.py python-dotenv PyPDF2 openai
   ```
   - Ensure `pip` matches your Python version (try `pip3` or `python3 -m pip` if needed).
   - Dependencies:
     - `discord.py`: Discord API interaction.
     - `python-dotenv`: Load `.env` variables.
     - `PyPDF2`: PDF text extraction.
     - `openai`: Grok API client (used with xAI endpoint).

4. **Run the Bot**
   ```bash
   python bot.py
   ```
   - Or use `python3 bot.py` if required.
   - The bot will log in, set its activity to “Change Me”, and start processing messages.

5. **Invite the Bot to Servers**
   - In the Discord Developer Portal, go to **OAuth2 > URL Generator**.
   - Select `bot` scope and the **Send Messages** permission.
   - Copy the generated URL and use it to invite the bot to your servers.
   - Ensure the bot has “Send Messages” permission in each server.

6. **Verify Bot Behavior**
   - Check console logs for startup:
     ```
     2025-05-18 21:36:45,123 - ERROR - ✅ Logged in as Bot#1234 (ID: 123456789012345678)
     ```
   - In Discord, test by:
     - Mentioning the bot: `@Bot What is AI?`
     - Replying to a bot message.
     - Uploading a PDF to process its text.
     - Requesting an image: `@Bot generate image of a cat`.
   - Confirm the bot’s activity is “Change Me” and responses are sent (text, image URLs, or error messages).
   - Logs show errors only (e.g., “Grok API error”, “PDF error”).

## Usage
- **Text Queries**: Mention the bot (e.g., `@Bot`) or reply to its messages with questions or prompts.
  - Simple questions (e.g., “What is AI?”) get 2-3 sentence responses (<350 chars).
  - Complex queries get detailed answers (<1800 chars).
- **Image Generation**: Use commands like “generate image of [description]” to get an image URL.
- **PDF Uploads**: Attach a PDF; the bot extracts text (up to 3000 chars, 5 pages) and processes it as the message content.
- **Image Uploads**: Upload `.jpg`, `.jpeg`, or `.png` files; the bot responds with “Image uploaded: [filename] (analysis not supported)”.

## Troubleshooting
- **Bot Doesn’t Start**
  - Check `.env` for correct `DISCORD_TOKEN` and `GROK_API_KEY`.
  - Verify dependencies: `pip install discord.py python-dotenv PyPDF2 openai`.
  - Ensure Python 3.8+: `python --version`.
  - Look for logs like “ValueError: Missing required environment variables”.

- **Bot Doesn’t Respond**
  - Check logs for “Grok API error” (invalid API key, quota exceeded) or “Error: ...”.
  - Ensure bot is mentioned (e.g., `@Bot`) or replied to.
  - Verify “Send Messages” permission in the server.
  - Test Grok API with a simple script (contact xAI for docs).

- **PDF Processing Fails**
  - Logs show “PDF error” or “No text extracted from PDF” if the PDF is empty or malformed.
  - Ensure the PDF has extractable text (not scanned images).
  - Try a different PDF or limit to 5 pages.

- **Image Generation Fails**
  - Logs show “Image generation error” for invalid prompts or API issues.
  - Ensure prompt starts with “generate/create/draw” and includes “image/picture/art” (e.g., “generate image of a cat”).
  - Check Grok API key and quota.

- **Logs**
  - All logs are console-only, using `logging.ERROR`.
  - Example errors: “Grok API error: Invalid API key”, “PDF error: Invalid PDF structure”.
  - Note: Login uses `logger.error` (unusual for non-errors, as coded).

## Contributing
- Fork the repository and submit pull requests for improvements.
- Suggest features (e.g., image analysis, custom activity via `.env`).

## License
MIT License. See [LICENSE](LICENSE) for details.
