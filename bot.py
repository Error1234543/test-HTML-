import os
import json
import time
from flask import Flask, request
import telebot
from telebot import types

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "<YOUR_BOT_TOKEN_HERE>"
OWNER_ID = int(os.getenv("OWNER_ID") or 7447651332)
WEBAPP_URL = "https://neetjeegujrati.netlify.app"   # Mini App URL
USERS_FILE = "users.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------------- LOAD USERS ----------------
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({"allowed": [OWNER_ID]}, f)

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------------- BOT COMMANDS ----------------
@bot.message_handler(commands=['start'])
def start(message):
    data = load_users()
    if message.from_user.id not in data["allowed"]:
        bot.reply_to(
            message,
            "❌ You are *NOT* an authorized user!\n\nBuy premium: t.me/Xdsonic",
            parse_mode="Markdown"
        )
        return

    keyboard = types.InlineKeyboardMarkup()
    web_btn = types.InlineKeyboardButton(
        text="🚀 Open NEET/JEE Gujarati App",
        web_app=types.WebAppInfo(WEBAPP_URL)
    )
    keyboard.add(web_btn)

    bot.send_message(
        message.chat.id,
        "Welcome to **NEET/JEE Gujarati Secure App** 🔐",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['add'])
def add_user(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only OWNER can add users!")
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: `/add 123456789`", parse_mode="Markdown")
        return

    try:
        user_id = int(parts[1])
    except:
        bot.reply_to(message, "❌ Invalid User ID!")
        return

    data = load_users()
    if user_id in data["allowed"]:
        bot.reply_to(message, "✔️ This user is already authorized!")
        return

    data["allowed"].append(user_id)
    save_users(data)
    bot.reply_to(message, f"✔️ User `{user_id}` added successfully!", parse_mode="Markdown")

@bot.message_handler(commands=['remove'])
def remove_user(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only OWNER can remove users!")
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: `/remove 123456789`", parse_mode="Markdown")
        return

    try:
        user_id = int(parts[1])
    except:
        bot.reply_to(message, "❌ Invalid User ID!")
        return

    data = load_users()
    if user_id not in data["allowed"]:
        bot.reply_to(message, "❌ This user is NOT in the list!")
        return

    data["allowed"].remove(user_id)
    save_users(data)
    bot.reply_to(message, f"🗑 User `{user_id}` removed successfully!", parse_mode="Markdown")

@bot.message_handler(commands=['auth'])
def auth_list(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only OWNER can check authorization list!")
        return

    data = load_users()
    text = "🔐 *Authorized Users List:*\n\n"
    text += "\n".join(f"• `{uid}`" for uid in data["allowed"])
    bot.reply_to(message, text, parse_mode="Markdown")

# ---------------- WEBHOOK HANDLER ----------------
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "Bot is running via Webhook!", 200

# ---------------- SAFE WEBHOOK SETUP ----------------
def setup_webhook():
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("⚠️ WEBHOOK_URL not set. Bot will not register webhook yet.")
        return

    while True:
        try:
            print("🔄 Removing old webhook...")
            bot.remove_webhook()
            print(f"⚙️ Setting new webhook: {WEBHOOK_URL}/{BOT_TOKEN}")
            bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
            print("✅ Webhook set successfully!")
            break
        except Exception as e:
            print("❌ Failed to set webhook. Retrying in 5 seconds...", e)
            time.sleep(5)

# ---------------- START SERVER ----------------
if __name__ == "__main__":
    # Setup webhook if URL exists
    setup_webhook()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)