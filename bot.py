import os
import json
import telebot
from telebot import types
from flask import Flask, request

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL", "https://neetjeegujrati.netlify.app")
MANIFEST_PATH = os.getenv("MANIFEST_PATH", "manifest.json")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OWNER_ID = os.getenv("OWNER_ID", "")
ALLOWED_GROUP = os.getenv("ALLOWED_GROUP", "")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


# ---------------- LOAD MANIFEST ----------------
def load_manifest():
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


# ---------------- START COMMAND ----------------
@bot.message_handler(commands=["start"])
def start(msg):
    kb = types.InlineKeyboardMarkup()

    # Buttons
    b1 = types.InlineKeyboardButton("📁 YAKEEN NEET GUJARATI 2026 TESTS", callback_data="yakeen")
    b2 = types.InlineKeyboardButton("📁 Lakshya", callback_data="lakshya")
    b3 = types.InlineKeyboardButton("📁 ALLEN TEST", callback_data="allen")
    b4 = types.InlineKeyboardButton("➡️ Open Test Site", url=BASE_URL)

    kb.add(b1)
    kb.add(b2)
    kb.add(b3)
    kb.add(b4)

    bot.send_message(
        msg.chat.id,
        "📘 *Select Test Category*",
        reply_markup=kb,
        parse_mode="Markdown"
    )


# --------------- CALLBACK HANDLER ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = load_manifest()

    if call.data == "yakeen":
        send_test_list(call.message.chat.id, data.get("YAKEEN NEET GUJARATI 2026 TESTS", []))

    elif call.data == "lakshya":
        send_test_list(call.message.chat.id, data.get("Lakshya", []))

    elif call.data == "allen":
        send_test_list(call.message.chat.id, data.get("ALLEN TEST", []))


# --------------- SEND TEST LIST ----------------
def send_test_list(chat_id, tests):
    if not tests:
        bot.send_message(chat_id, "⚠️ No tests available!")
        return

    for t in tests:
        name = t.get("name", "Test")
        file = t.get("file", "")

        link = f"{BASE_URL}/quiz.html?test={file}"

        text = f"📝 *{name}*\n➡️ {link}"
        bot.send_message(chat_id, text, parse_mode="Markdown")


# ---------------- WEBHOOK SETUP ----------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


# ---------------- MAIN ----------------
if __name__ == "__main__":
    if not WEBHOOK_URL:
        print("⚠️ WEBHOOK_URL not set! Set after first deploy.")
    else:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)

    app.run(host="0.0.0.0", port=10000)