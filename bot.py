import os
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Will set after deploy

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# DELETE WEBHOOK FIRST
try:
    bot.delete_webhook()
except:
    pass

# SET WEBHOOK IF URL PROVIDED
if WEBHOOK_URL:
    bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook set to:", WEBHOOK_URL)
else:
    print("⚠️ WEBHOOK_URL not set yet! Set after deploy.")


@app.route('/webhook', methods=['POST'])
def receive_webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🚀 Webhook bot running on Render!")


@bot.message_handler(func=lambda m: True)
def echo(msg):
    bot.reply_to(msg, msg.text)


# Flask app — DO NOT remove
@app.route('/')
def home():
    return "Bot Running!", 200