# Courtside Basketball Chatbot

A responsive basketball chatbot powered by the OpenAI API. It can handle open-ended questions and keeps conversation context for the current browser session.

## Setup

1. Create an OpenAI API key in your OpenAI developer account. API usage may incur charges; a ChatGPT subscription does not automatically include API credit.
2. From this folder, create a local environment file:

   ```sh
   cp .env.example .env
   ```

3. Open `.env` and replace `your_api_key_here` with your API key. Keep this file private; it is excluded by `.gitignore`.
4. Start the local server:

   ```sh
   python3 server.py
   ```

5. Open [http://127.0.0.1:8080](http://127.0.0.1:8080). Stop the server with Ctrl+C.

## Privacy and limitations

- The API key stays in the local server's `.env`; it is never sent to the browser.
- Chat messages are sent to OpenAI to generate answers. This site does not save conversation history; it only keeps context in browser memory until the page is refreshed or closed.
- The assistant has no web search or live game feed, so it cannot reliably provide current scores, schedules, standings, or breaking news.
- Do not enter sensitive personal information. Review OpenAI's current API data-handling terms before use.
- The development server binds to `127.0.0.1` and is intended for local use, not public hosting.
