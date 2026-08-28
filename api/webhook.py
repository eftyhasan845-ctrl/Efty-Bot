import os
import json
import re
import requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ["BOT_TOKEN"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SMS_API = "https://api.g-sheba.top/csms/haf.php"

PHONE_RE = re.compile(r"^01[3-9]\d{8}$")


def telegram(method, data=None):
    r = requests.post(
        f"{TELEGRAM_API}/{method}",
        json=data or {},
        timeout=15
    )
    return r.json()


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram("sendMessage", data)


def main_menu():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📨 Send SMS",
                    "callback_data": "send_sms"
                }
            ],
            [
                {
                    "text": "👨‍💻 Developer: Efty67",
                    "callback_data": "developer"
                }
            ]
        ]
    }


def handle_start(chat_id):
    send_message(
        chat_id,
        "🤖 Efty SMS Bot\n\n"
        "নিচের button থেকে SMS পাঠানো শুরু করুন।",
        main_menu()
    )


def handle_callback(callback):
    callback_id = callback["id"]
    data = callback.get("data", "")
    message = callback.get("message", {})

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    telegram("answerCallbackQuery", {
        "callback_query_id": callback_id
    })

    if data == "developer":
        send_message(
            chat_id,
            "👨‍💻 Developer: Efty67\n"
            "📞 Contact: @Efty67",
            main_menu()
        )

    elif data == "send_sms":
        send_message(
            chat_id,
            "📱 Step 1/2\n\n"
            "Receiver-এর বাংলাদেশি mobile number পাঠান।\n\n"
            "Example:\n"
            "01712345678"
        )


def process_text(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text == "/start":
        handle_start(chat_id)
        return

    # User replied to a bot prompt
    replied = message.get("reply_to_message")

    if replied:
        replied_text = replied.get("text", "")

        # Step 2: SMS message
        if replied_text.startswith("📱 Number accepted:"):
            number = replied_text.split(":", 1)[1].strip()

            if not PHONE_RE.fullmatch(number):
                send_message(chat_id, "❌ Invalid number.")
                return

            if not text:
                send_message(chat_id, "❌ Message খালি হতে পারবে না।")
                return

            if len(text) > 500:
                send_message(
                    chat_id,
                    "❌ Message maximum 500 characters হতে পারবে।"
                )
                return

            confirmation = (
                "📋 SMS Confirmation\n\n"
                f"📱 Number: {number}\n\n"
                f"✉️ Message:\n{text}\n\n"
                "উপরের SMS পাঠাতে চাইলে এই message-এ "
                "YES reply করুন।\n\n"
                "Cancel করতে NO reply করুন।"
            )

            send_message(chat_id, confirmation)
            return

        # Step 3: Confirmation
        if replied_text.startswith("📋 SMS Confirmation"):
            answer = text.lower()

            if answer not in ("yes", "no"):
                send_message(
                    chat_id,
                    "⚠️ এই message-এ শুধু YES অথবা NO reply করুন।"
                )
                return

            if answer == "no":
                send_message(
                    chat_id,
                    "❌ SMS cancelled.",
                    main_menu()
                )
                return

            # Parse number
            number_match = re.search(
                r"📱 Number:\s*(01[3-9]\d{8})",
                replied_text
            )

            # Parse message
            message_match = re.search(
                r"✉️ Message:\n(.*?)\n\nউপরের SMS",
                replied_text,
                re.S
            )

            if not number_match or not message_match:
                send_message(
                    chat_id,
                    "❌ Confirmation data পাওয়া যায়নি। আবার /start দিন।"
                )
                return

            number = number_match.group(1)
            sms = message_match.group(1)

            try:
                response = requests.get(
                    SMS_API,
                    params={
                        "number": number,
                        "sms": sms
                    },
                    timeout=15
                )

                if response.ok:
                    result = response.text[:1500]

                    send_message(
                        chat_id,
                        "✅ API Request Completed!\n\n"
                        f"📱 Number: {number}\n"
                        f"✉️ Message: {sms}\n\n"
                        f"API Response:\n{result}",
                        main_menu()
                    )
                else:
                    send_message(
                        chat_id,
                        f"❌ API Error\nHTTP Status: {response.status_code}",
                        main_menu()
                    )

            except Exception as e:
                send_message(
                    chat_id,
                    "❌ API connection failed.\n\n"
                    f"{str(e)[:500]}",
                    main_menu()
                )

            return

    # Step 1: number
    if PHONE_RE.fullmatch(text):
        send_message(
            chat_id,
            f"📱 Number accepted: {text}\n\n"
            "✉️ Step 2/2\n\n"
            "এখন এই message-এ Reply করে আপনার SMS লিখুন।"
        )
        return

    send_message(
        chat_id,
        "⚠️ বুঝতে পারিনি। /start দিন।"
    )


def process_update(update):
    if "callback_query" in update:
        handle_callback(update["callback_query"])

    elif "message" in update:
        process_text(update["message"])


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Efty SMS Bot is running!"
        )

    def do_POST(self):
        try:
            length = int(
                self.headers.get("Content-Length", 0)
            )

            body = self.rfile.read(length)
            update = json.loads(body.decode("utf-8"))

            process_update(update)

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json"
            )
            self.end_headers()

            self.wfile.write(
                b'{"ok":true}'
            )

        except Exception as e:
            self.send_response(500)
            self.send_header(
                "Content-Type",
                "application/json"
            )
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    "ok": False,
                    "error": str(e)
                }).encode()
            )
