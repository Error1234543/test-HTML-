import telebot
from telebot import types
import json
import os

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = "https://neetjeegujrati.netlify.app"   # ⭐ Your Mini-App Website
OWNER_ID = int(os.getenv("OWNER_ID", 7447651332))
USERS_FILE = "users.json"

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- LOAD AUTH USERS ----------------
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({"allowed": [OWNER_ID]}, f)

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    data = load_users()

    if message.from_user.id not in data["allowed"]:
        bot.reply_to(
            message,
            "❌ You are *NOT* an authorized user!\n\nBuy premium: t.me/sonic8307",
            parse_mode="Markdown"
        )
        return

    # Mini App Button
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


# ---------------- /add userID ----------------
@bot.message_handler(commands=['add'])
def add_user(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only OWNER can add users!")
        return

    try:
        user_id = int(message.text.split()[1])
    except:
        bot.reply_to(message, "Usage: `/add 123456789`", parse_mode="Markdown")
        return

    data = load_users()

    if user_id in data["allowed"]:
        bot.reply_to(message, "✔️ This user is already authorized!")
        return

    data["allowed"].append(user_id)
    save_users(data)

    bot.reply_to(message, f"✔️ User {user_id} added successfully!")


# ---------------- /auth list ----------------
@bot.message_handler(commands=['auth'])
def auth_list(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only OWNER can check authorization list!")
        return

    data = load_users()
    text = "🔐 *Authorized Users:*\n\n"
    text += "\n".join(str(uid) for uid in data["allowed"])

    bot.reply_to(message, text, parse_mode="Markdown")


# ---------------- RUN BOT ----------------
print("BOT is running...")
bot.infinity_polling(skip_pending=True)