
#!/usr/bin/env python3
"""
Telegram Mini-App Bot for opening your hosted quiz pages (index/quiz).
Usage: fill .env, install requirements, run.
"""
import os
import json
import logging
import urllib.parse
from typing import Dict, List

from telebot import TeleBot, types
from dotenv import load_dotenv

# load env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BASE_URL = os.getenv("BASE_URL", "").strip() or "https://neetjeegujrati.netlify.app"
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None
ALLOWED_GROUP = int(os.getenv("ALLOWED_GROUP", "0")) if os.getenv("ALLOWED_GROUP") else None
MANIFEST_PATH = os.getenv("MANIFEST_PATH", "manifest.json")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

bot = TeleBot(BOT_TOKEN, parse_mode="Markdown")

# load manifest.json
def load_manifest(path: str) -> Dict[str, List[Dict]]:
    if not os.path.exists(path):
        logger.error("Manifest file not found: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

manifest = load_manifest(MANIFEST_PATH)


# helper to ensure callback_data is safe
def safe_cb(s: str) -> str:
    # use quote_plus to preserve spaces and special chars
    return urllib.parse.quote_plus(s)


def unsafed_cb(s: str) -> str:
    return urllib.parse.unquote_plus(s)


# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["start", "menu"])
def cmd_start(msg: types.Message):
    # optional group restriction
    if ALLOWED_GROUP and msg.chat.type in ("private", "group", "supergroup"):
        # if in private chat we allow, otherwise if group check
        pass  # no action; we will enforce for web buttons if desired

    kb = types.InlineKeyboardMarkup()
    if not manifest:
        bot.send_message(msg.chat.id, "❗️ No tests available (manifest empty).")
        return

    # Add folders
    for folder in manifest.keys():
        kb.add(types.InlineKeyboardButton(text=folder, callback_data=f"folder:{safe_cb(folder)}"))

    # Add direct "Open Website" button
    kb.add(types.InlineKeyboardButton(text="Open Test Site", url=BASE_URL))

    bot.send_message(msg.chat.id, "📁 *Select Test Category*", reply_markup=kb)


# ---------------- CALLBACKS ----------------
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("folder:"))
def cb_folder(call: types.CallbackQuery):
    try:
        folder_raw = call.data.split(":", 1)[1]
        folder = unsafed_cb(folder_raw)
        tests = manifest.get(folder)
        if tests is None:
            bot.answer_callback_query(call.id, "Folder not found.", show_alert=True)
            return

        kb = types.InlineKeyboardMarkup(row_width=1)

        for t in tests:
            # build final URL
            test_file = t.get("file", "")
            # Encode the test file part to be safe in URL query param
            encoded_test = urllib.parse.quote(test_file, safe="/:?=&")
            test_url = f"{BASE_URL.rstrip('/')}/quiz.html?test={encoded_test}"

            # If you want to restrict opening tests to a certain group, you can check here:
            # For WebApp button, telebot supports web_app parameter (TeleBot >= 4.x).
            kb.add(types.InlineKeyboardButton(text=t.get("name", "Test"), web_app=types.WebAppInfo(url=test_url)))

        # Back button
        kb.add(types.InlineKeyboardButton(text="⬅ Back", callback_data="back:"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📝 *{folder} — Select Test*",
            reply_markup=kb
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.exception("cb_folder error: %s", e)
        bot.answer_callback_query(call.id, "Error opening folder.")


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("back:"))
def cb_back(call: types.CallbackQuery):
    # re-show folders
    kb = types.InlineKeyboardMarkup()
    for folder in manifest.keys():
        kb.add(types.InlineKeyboardButton(text=folder, callback_data=f"folder:{safe_cb(folder)}"))
    kb.add(types.InlineKeyboardButton(text="Open Test Site", url=BASE_URL))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📁 *Select Test Category*",
        reply_markup=kb
    )
    bot.answer_callback_query(call.id)


# ---------------- ADMIN OPTIONAL ----------------
@bot.message_handler(commands=["reload_manifest"])
def cmd_reload_manifest(msg: types.Message):
    # allow only owner
    if OWNER_ID and msg.from_user.id != OWNER_ID:
        bot.reply_to(msg, "Unauthorized.")
        return
    global manifest
    manifest = load_manifest(MANIFEST_PATH)
    bot.reply_to(msg, "Manifest reloaded.")


# ---------------- START POLLING ----------------
if __name__ == "__main__":
    logger.info("Bot starting...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)