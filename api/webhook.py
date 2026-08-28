import os
import re
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["8479494858:AAHmQX9CQ09rF9mM0nAhfLQrev438S_FOa8"]

API_URL = "https://api.g-sheba.top/csms/haf.php"

PHONE_RE = re.compile(r"^01[3-9]\d{8}$")


def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📨 Send SMS",
                callback_data="send_sms"
            )
        ],
        [
            InlineKeyboardButton(
                "👨‍💻 Developer: Efty67",
                callback_data="developer"
            )
        ]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "🤖 Efty SMS Bot\n\n"
        "নিচের button থেকে SMS পাঠানো শুরু করুন।",
        reply_markup=menu()
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "developer":
        await query.message.reply_text(
            "👨‍💻 Developer: Efty67\n"
            "📞 Contact: @Efty67",
            reply_markup=menu()
        )

    elif query.data == "send_sms":
        context.user_data["step"] = "phone"

        await query.message.reply_text(
            "📱 Receiver number দিন:\n\n"
            "Example: `01712345678`",
            parse_mode="Markdown"
        )


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    if step == "phone":

        phone = update.message.text.strip()
        phone = phone.replace(" ", "").replace("-", "")

        if not PHONE_RE.fullmatch(phone):
            await update.message.reply_text(
                "❌ ভুল নম্বর।\n\n"
                "বাংলাদেশি 11 digit mobile number দিন।\n"
                "Example: 01712345678"
            )
            return

        context.user_data["phone"] = phone
        context.user_data["step"] = "message"

        await update.message.reply_text(
            "✉️ এখন SMS message লিখুন:"
        )

    elif step == "message":

        sms = update.message.text.strip()

        if not sms:
            await update.message.reply_text(
                "❌ Message খালি রাখা যাবে না।"
            )
            return

        if len(sms) > 500:
            await update.message.reply_text(
                "❌ Message সর্বোচ্চ 500 characters হতে পারবে।"
            )
            return

        context.user_data["sms"] = sms
        context.user_data["step"] = "confirm"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Send",
                    callback_data="confirm_send"
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="cancel"
                )
            ]
        ])

        await update.message.reply_text(
            "📋 *SMS Details*\n\n"
            f"📱 Number: `{context.user_data['phone']}`\n"
            f"✉️ Message: `{sms}`\n\n"
            "Send করবেন?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":

        context.user_data.clear()

        await query.message.reply_text(
            "❌ Cancelled.",
            reply_markup=menu()
        )

        return

    if query.data != "confirm_send":
        return

    phone = context.user_data.get("phone")
    sms = context.user_data.get("sms")

    if not phone or not sms:

        await query.message.reply_text(
            "⚠️ Session expired.\n"
            "আবার /start দিন।"
        )

        return

    try:

        response = requests.get(
            API_URL,
            params={
                "number": phone,
                "sms": sms
            },
            timeout=15
        )

        if response.ok:

            result = response.text[:1000]

            await query.message.reply_text(
                "✅ API Request Sent!\n\n"
                f"📱 Number: {phone}\n"
                f"✉️ Message: {sms}\n\n"
                f"API Response:\n{result}",
                reply_markup=menu()
            )

        else:

            await query.message.reply_text(
                f"❌ API Error: HTTP {response.status_code}",
                reply_markup=menu()
            )

    except Exception as e:

        await query.message.reply_text(
            f"❌ Request failed:\n{str(e)[:500]}",
            reply_markup=menu()
        )

    finally:

        context.user_data.clear()


# Telegram application
application = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

application.add_handler(
    CommandHandler("start", start)
)

application.add_handler(
    CallbackQueryHandler(
        confirm,
        pattern="^(confirm_send|cancel)$"
    )
)

application.add_handler(
    CallbackQueryHandler(
        buttons,
        pattern="^(send_sms|developer)$"
    )
)

application.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        messages
    )
)


async def process_update(request):

    data = await request.json()

    update = Update.de_json(
        data,
        application.bot
    )

    await application.initialize()
    await application.process_update(update)
    await application.shutdown()


# Vercel Python Function
async def handler(request):

    if request.method != "POST":
        return {
            "statusCode": 200,
            "body": "Efty SMS Bot is running!"
        }

    try:

        await process_update(request)

        return {
            "statusCode": 200,
            "body": "OK"
        }

    except Exception as e:

        return {
            "statusCode": 500,
            "body": str(e)
        }
