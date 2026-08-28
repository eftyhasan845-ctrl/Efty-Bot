import os
import json
import re
import time
import requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ["8479494858:AAHmQX9CQ09rF9mM0nAhfLQrev438S_FOa8"]

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SMS_API = "https://api.g-sheba.top/csms/haf.php"

PHONE_RE = re.compile(r"^01[3-9]\d{8}$")

# Simple per-function-instance cooldown
last_send = {}


def tg(method, payload):
    return requests.post(
        f"{TG_API}/{method}",
        json=payload,
        timeout=15
    )


def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    tg("sendMessage", payload)


def menu():
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


def process_update(update):

    # Button click
    if "callback_query" in update:

        q = update["callback_query"]
        chat_id = q["message"]["chat"]["id"]
        action = q.get("data")

        tg("answerCallbackQuery", {
            "callback_query_id": q["id"]
        })

        if action == "developer":
            send_message(
                chat_id,
                "👨‍💻 Developer: Efty67\n"
                "📞 Contact: @Efty67",
                menu()
            )

        elif action == "send_sms":
            send_message(
                chat_id,
                "📱 Receiver number দিন:\n\n"
                "Example: 01712345678"
            )

        return

    # Normal message
    message = update.get("message")

    if not message:
        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text == "/start":
        send_message(
            chat_id,
            "🤖 Efty SMS Bot\n\n"
            "নিচের button ব্যবহার করুন।",
            menu()
        )
        return

    # Number input
    if PHONE_RE.fullmatch(text):

        send_message(
            chat_id,
            f"📱 Number accepted: {text}\n\n"
            "এখন SMS message লিখুন।\n"
            "তারপর পাঠানোর আগে confirmation নেওয়া হবে।"
        )
        return

    # SMS input only when replying to accepted-number message
    reply = message.get("reply_to_message")

    if reply and reply.get("text", "").startswith("📱 Number accepted:"):

        number = reply["text"].split(":", 1)[1].strip()

        if not PHONE_RE.fullmatch(number):
            send_message(chat_id, "❌ Invalid number.")
            return

        if not text:
            send_message(chat_id, "❌ Message empty.")
            return

        if len(text) > 500:
            send_message(
                chat_id,
                "❌ Message maximum 500 characters."
            )
            return

        confirmation = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Confirm",
                        "callback_data": f"send:{number}"
                    },
                    {
                        "text": "❌ Cancel",
                        "callback_data": "cancel"
                    }
                ]
            ]
        }

        send_message(
            chat_id,
            f"📋 Confirm SMS\n\n"
            f"📱 Number: {number}\n"
            f"✉️ Message: {text}\n\n"
            "Send করবেন?",
            confirmation
        )

        return


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Efty SMS Bot is running."
        )

    def do_POST(self):

        try:

            length = int(
                self.headers.get("Content-Length", "0")
            )

            body = self.rfile.read(length)
            update = json.loads(body.decode("utf-8"))

            # Handle confirmation buttons separately
            if "callback_query" in update:

                q = update["callback_query"]
                action = q.get("data", "")
                chat_id = q["message"]["chat"]["id"]

                tg("answerCallbackQuery", {
                    "callback_query_id": q["id"]
                })

                if action == "cancel":

                    send_message(
                        chat_id,
                        "❌ Cancelled.",
                        menu()
                    )

                elif action.startswith("send:"):

                    number = action.split(":", 1)[1]

                    # Cooldown
                    now = time.time()
                    previous = last_send.get(chat_id, 0)

                    if now - previous < 30:
                        send_message(
                            chat_id,
                            "⏳ Please wait 30 seconds before another send."
                        )
                    else:

                        # Telegram callback does not contain the SMS text,
                        # so ask user to reply with the exact message.
                        send_message(
                            chat_id,
                            f"📱 Number: {number}\n\n"
                            "শেষ ধাপ: এই message-এ Reply করে SMS text লিখুন।"
                        )

                        # Store pending number in a temporary Telegram message
                        # flow is intentionally confirmation-based.

                else:
                    process_update(update)

            else:
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

        except Exception as exc:

            print("ERROR:", exc)

            self.send_response(500)
            self.send_header(
                "Content-Type",
                "application/json"
            )
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    "ok": False,
                    "error": str(exc)
                }).encode()
            )
