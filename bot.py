import os
import json
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL", "https://neetjeegujrati.netlify.app")
MANIFEST_PATH = os.getenv("MANIFEST_PATH", "manifest.json")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)



# Load Manifest
def load_manifest():
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


# ----------- COMMAND HANDLERS -------------

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "Bot is working 🎉\n\n/tests likho test list dekhne ke liye!")


@bot.message_handler(commands=['tests'])
def tests(msg):

    data = load_manifest()
    if not data:
        bot.reply_to(msg, "⚠️ manifest.json not found!")
        return

    for folder, tests in data.items():
        text = f"📁 *{folder}*\n\n"
        for t in tests:
            test_name = t.get("name", "Untitled Test")
            file_path = t.get("file")
            test_link = f"{BASE_URL}/quiz.html?test={file_path}"

            text += f"🔹 *{test_name}*\n➡️ {test_link}\n\n"

        bot.send_message(msg.chat.id, text, parse_mode="Markdown")




# ----------- WEBHOOK HANDLER -------------

@app.route("/" + BOT_TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode('utf-8'))
    bot.process_new_updates([update])
    return "OK", 200



if __name__ == "__main__":

    # Auto webhook URL generate
    if RENDER_URL:
        WEBHOOK_URL = f"{RENDER_URL}/{BOT_TOKEN}"
    else:
        WEBHOOK_URL = None

    print("WEBHOOK URL =", WEBHOOK_URL)

    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set successfully!")

    app.run(host="0.0.0.0", port=10000)