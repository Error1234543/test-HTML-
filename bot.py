import os
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Example: https://yourrenderdomain.onrender.com/webhook

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# -------------------------------------
# SET/DELETE WEBHOOK
# -------------------------------------
bot.delete_webhook()

bot.set_webhook(url=f"{WEBHOOK_URL}")

print("Webhook set successfully:", WEBHOOK_URL)


# -------------------------------------
# FLASK ROUTE FOR TELEGRAM
# -------------------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


# -------------------------------------
# TEST COMMAND
# -------------------------------------
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🚀 Bot is live with webhook!")


# -------------------------------------
# NORMAL MESSAGE
# -------------------------------------
@bot.message_handler(func=lambda m: True)
def echo(msg):
    bot.reply_to(msg, "You said: " + msg.text)


# -------------------------------------
# FLASK START
# -------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)