import json
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parent
OPENAI_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_REQUEST_BYTES = 48_000
MAX_MESSAGES = 16
MAX_MESSAGE_CHARS = 2_000

SYSTEM_PROMPT = (
    "You are Coach Courtside, a friendly and knowledgeable basketball assistant. "
    "Answer naturally and helpfully, including open-ended questions beyond basketball. "
    "Be clear when you are uncertain. You do not have web search or live game data, so "
    "never invent current scores, schedules, standings, injuries, or breaking news. "
    "For training or injury questions, give general information and encourage a qualified "
    "coach or medical professional when appropriate. Keep most answers concise."
)


class APIError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def load_local_env():
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        return
    for line_number, raw_line in enumerate(env_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            raise ValueError(f"Invalid .env entry on line {line_number}. Expected KEY=VALUE.")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def validate_messages(value):
    if not isinstance(value, list) or not value or len(value) > MAX_MESSAGES:
        raise APIError(400, f"Send between 1 and {MAX_MESSAGES} chat messages.")

    messages = []
    total_chars = 0
    for message in value:
        if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
            raise APIError(400, "Chat messages must have a user or assistant role.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise APIError(400, "Chat message content must not be empty.")
        if len(content) > MAX_MESSAGE_CHARS:
            raise APIError(400, f"Each message must be {MAX_MESSAGE_CHARS} characters or fewer.")
        total_chars += len(content)
        messages.append({"role": message["role"], "content": content})

    if total_chars > MAX_REQUEST_BYTES:
        raise APIError(413, "This conversation is too long. Start a new chat.")
    if messages[-1]["role"] != "user":
        raise APIError(400, "The latest chat message must be from the user.")
    return messages


def request_openai(messages):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise APIError(503, "Add your OpenAI API key to the local .env file, then restart the server.")

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    payload = json.dumps(
        {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": messages,
            "max_output_tokens": 600,
        }
    ).encode("utf-8")
    request = Request(
        OPENAI_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise APIError(502, "OpenAI rejected the API key. Check OPENAI_API_KEY in .env.") from None
        if error.code == 429:
            raise APIError(429, "OpenAI rate limit or billing limit reached. Check your API account.") from None
        if error.code in (400, 404):
            raise APIError(502, "OpenAI rejected the request. Check OPENAI_MODEL in .env.") from None
        raise APIError(502, f"OpenAI returned an error (HTTP {error.code}). Try again later.") from None
    except (URLError, TimeoutError):
        raise APIError(502, "Could not reach OpenAI. Check your internet connection and try again.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise APIError(502, "OpenAI returned an unreadable response. Please try again.") from None

    if not isinstance(result, dict) or not isinstance(result.get("output"), list):
        raise APIError(502, "OpenAI returned an unexpected response. Please try again.")

    output = []
    for item in result.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                output.append(content["text"])
    reply = "\n".join(output).strip()
    if not reply:
        raise APIError(502, "OpenAI returned no text. Please try again.")
    return reply


class ChatbotHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def end_headers(self):
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        path_parts = Path(path).parts
        if any(part.startswith(".") for part in path_parts) or path == "/server.py":
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != "/api/chat":
            self.send_json(404, {"error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid request length."})
            return
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self.send_json(413, {"error": "Request is empty or too large."})
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Request body must be valid JSON."})
            return
        if not isinstance(payload, dict):
            self.send_json(400, {"error": "Request body must be a JSON object."})
            return

        try:
            messages = validate_messages(payload.get("messages"))
            reply = request_openai(messages)
        except APIError as error:
            self.send_json(error.status, {"error": str(error)})
            return
        self.send_json(200, {"reply": reply})


def main():
    load_local_env()
    server = ThreadingHTTPServer(("127.0.0.1", 8080), ChatbotHandler)
    print("Courtside running at http://127.0.0.1:8080 (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Could not start Courtside: {error}", file=sys.stderr)
        raise SystemExit(1)
