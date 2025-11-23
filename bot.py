import os
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route("/" + BOT_TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# Test command
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "Bot is working 🎉")

if __name__ == "__main__":

    # Auto-generate webhook URL
    if RENDER_URL:
        WEBHOOK_URL = f"{RENDER_URL}/{BOT_TOKEN}"
    else:
        WEBHOOK_URL = None

    print("WEBHOOK URL =", WEBHOOK_URL)

    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set successfully!")

    # Flask server
    app.run(host="0.0.0.0", port=10000)