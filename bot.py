
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# ---------------- LOAD JSON ----------------
with open("fest.json", "r", encoding="utf-8") as f:
    TEST_DATA = json.load(f)

# ------------- START COMMAND ----------------
@bot.message_handler(commands=['start'])
def start(message):
    kb = InlineKeyboardMarkup()

    for folder_name in TEST_DATA.keys():
        kb.add(
            InlineKeyboardButton(
                text=folder_name,
                callback_data=f"folder:{folder_name}"
            )
        )

    bot.send_message(
        message.chat.id,
        "📚 *Select Test Folder*",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# ------------- SHOW TEST LIST ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("folder:"))
def show_tests(call):
    folder = call.data.split("folder:")[1]

    tests = TEST_DATA[folder]

    kb = InlineKeyboardMarkup()
    for t in tests:
        kb.add(
            InlineKeyboardButton(
                text=t["name"],
                callback_data=f"test:{t['file']}"
            )
        )

    bot.edit_message_text(
        f"📁 *{folder}* → Select Test",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="Markdown"
    )

# ------------- OPEN TEST (WEB APP) ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("test:"))
def open_test(call):
    file_path = call.data.split("test:")[1]

    # Mini App URL
    webapp_url = f"{WEBHOOK_URL}/view?file={file_path}"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            text="📄 Open Test",
            web_app={"url": webapp_url}
        )
    )

    bot.edit_message_text(
        f"📝 *Your Test:* {file_path}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="Markdown"
    )

# ------------- FLASK ENDPOINT (Mini App Data Loader) ----------------
@server.route('/view')
def serve_test():
    file = request.args.get("file", "")

    if not os.path.exists(file):
        return f"<h1>❌ File Not Found: {file}</h1>"

    with open(file, "r", encoding="utf-8") as f:
        data = f.read()

    return f"""
    <html>
    <head>
        <title>KRIVA Test Viewer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial; padding:20px; }}
            pre {{ white-space: pre-wrap; background:#f1f1f1; padding:15px; border-radius:8px; }}
        </style>
    </head>
    <body>
        <h2>📘 Test File: {file}</h2>
        <pre>{data}</pre>
    </body>
    </html>
    """

# ------------------ WEBHOOK SETUP ----------------------
@server.route('/' + TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([
        telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    ])
    return "ok", 200

@server.route('/')
def index():
    return "Bot running OK!"

if __name__ == "__main__":
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    server.run(host="0.0.0.0", port=10000)