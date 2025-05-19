# Grok Discord Bot

A Discord bot powered by xAI's Grok API, designed to respond to user queries, process PDF attachments, and maintain conversation history. The bot responds to mentions or replies, handles text-based questions, and extracts text from PDFs for further processing. Image handling and generation are not supported.

## Features
- **Text Responses**: Answers user queries using the Grok API, with concise responses for simple questions and detailed answers for complex ones.
- **PDF Processing**: Extracts text from uploaded PDF files (up to 5 pages, 3000 characters) and responds based on the content.
- **Conversation History**: Maintains user-specific conversation history per channel, capped at 100,000 characters.
- **Error Handling**: Logs errors and provides user-friendly error messages for API issues or invalid inputs.
- **Restricted Image Handling**: Ignores images unless directly sent to the bot, replying with "Image handling is not supported." Ignores image generation requests with "Image generation is not supported."

## Prerequisites
- Python 3.8 or higher
- Discord bot token (obtain from [Discord Developer Portal](https://discord.com/developers/applications))
- xAI Grok API key (obtain from [xAI](https://x.ai/api))
- Required Python packages:
  - `discord.py`
  - `PyPDF2`
  - `python-dotenv`
  - `openai`

## Installation
1. **Clone the Repository** (or download the code):
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```
2. **Install Dependencies**:
   ```bash
   pip install discord.py PyPDF2 python-dotenv openai
   ```
3. **Set Up Environment Variables**:
   - Create a `.env` file in the project root.
   - Add the following:
     ```env
     DISCORD_TOKEN=your_discord_bot_token
     GROK_API_KEY=your_grok_api_key
     ```
   - Replace `your_discord_bot_token` and `your_grok_api_key` with your actual tokens.
4. **Run the Bot**:
   ```bash
   python bot.py
   ```

## Usage
1. **Invite the Bot**:
   - Add the bot to your Discord server using the OAuth2 URL generated in the Discord Developer Portal (ensure `bot` scope and permissions for `Send Messages`, `Read Messages`, and `Read Message History`).
2. **Interact with the Bot**:
   - **Mention the Bot**: Use `@BotName <query>` to ask a question or upload a PDF.
   - **Reply to the Bot**: Reply to a bot message to continue the conversation.
   - **Upload PDFs**: Attach a PDF file with a mention or reply to process its content.
   - **Image Restrictions**: If an image is uploaded directly, the bot replies "Image handling is not supported." Image generation requests (e.g., "generate an image") receive "Image generation is not supported."
3. **Examples**:
   - `@BotName What is the capital of France?` → Responds with a short answer.
   - `@BotName Explain quantum mechanics` → Provides a concise explanation.
   - `@BotName` with a PDF attachment → Extracts and processes PDF text.
   - `@BotName generate an image of a cat` → Replies "Image generation is not supported."
   - `@BotName` with a `.png` attachment → Replies "Image handling is not supported."

## Configuration
The bot uses the following constants (defined in `bot.py`):
- `MODEL`: `grok-3-beta` (Grok model for text responses).
- `MAX_RESPONSE_TOKENS`: 400 (max tokens for Grok responses).
- `DISCORD_MAX_CHARS`: 1800 (max characters for Discord messages).
- `MAX_HISTORY_CHARS`: 100,000 (max characters for conversation history).

## Limitations
- **Image Support**: The bot does not process or generate images, responding with appropriate messages for such requests.
- **PDF Limits**: Processes up to 5 pages or 3000 characters from PDFs.
- **API Dependency**: Requires a valid xAI Grok API key and stable internet connection.
- **Discord Limits**: Responses are capped at 1800 characters due to Discord's message length restrictions.

## Troubleshooting
- **Bot Not Responding**:
  - Check the console for error logs (errors are logged with timestamps).
  - Ensure `DISCORD_TOKEN` and `GROK_API_KEY` are correctly set in `.env`.
  - Verify the bot has necessary Discord permissions.
- **PDF Errors**: Ensure the PDF is not corrupted or password-protected.
- **API Errors**: Confirm your Grok API key is valid and has sufficient quota (see [xAI API](https://x.ai/api)).

## Contributing
Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/YourFeature`).
3. Commit changes (`git commit -m 'Add YourFeature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details (if applicable).

## Contact
For issues or feature requests, create an issue on the repository or contact the maintainer.
