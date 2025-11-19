import os
import re
import fitz
import google.generativeai as genai
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters, CommandHandler
from telegram.ext import CallbackContext

# -------------------------
#   ENV Variables
# -------------------------
TOKEN = os.getenv("8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k")
GEMINI_KEY = os.getenv("AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8")

if not TOKEN or not GEMINI_KEY:
    raise ValueError("ERROR: Please set GEMINI_API_KEY and TELEGRAM_TOKEN in environment variables!")

# Configure Gemini
genai.configure(api_key=GEMINI_KEY)

app = Flask(__name__)
bot = Bot(token=TOKEN)


# -------------------------
#   PDF Extract
# -------------------------
def extract_text_without_answer_key(file_bytes):
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    full_text = ""

    for page in pdf:
        full_text += page.get_text()

    pdf.close()

    # Remove Answer Key region
    patterns = [
        r"ANSWER KEY.*",  
        r"ANSWERS.*",
        r"SOLUTION.*",
        r"CORRECT ANSWERS.*",
        r"ANSWER SHEET.*",
        r"KEY:\s*.*",
        r"\bQ\s*\d+\s*-\s*[A-D]\b",  
    ]

    for p in patterns:
        full_text = re.sub(p, "", full_text, flags=re.IGNORECASE | re.DOTALL)

    return full_text.strip()


# -------------------------
#   Generate MCQ using AI
# -------------------------
def generate_quiz(text):
    prompt = f"""
Extract MCQ questions strictly from this text.
Ignore any answer key completely.
Output should be in clean format:

Q1. question text
A) option
B) option
C) option
D) option
Correct: A

Text:
{text}
"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text


# -------------------------
#   Start Command
# -------------------------
def start(update: Update, context: CallbackContext):
    update.message.reply_text("PDF bhejo, main MCQ bana dunga 😎")


# -------------------------
#   PDF Upload Handler
# -------------------------
def handle_pdf(update: Update, context: CallbackContext):
    file = update.message.document

    if not file.file_name.endswith(".pdf"):
        update.message.reply_text("Sirf PDF upload karo 😁")
        return

    file_bytes = file.get_file().download_as_bytearray()

    update.message.reply_text("⏳ Extracting PDF...")

    clean_text = extract_text_without_answer_key(file_bytes)

    update.message.reply_text("🤖 Generating MCQs...")

    quiz = generate_quiz(clean_text)

    update.message.reply_text("✅ Quiz Ready!\n\n" + quiz)


# -------------------------
#   Webhook Route
# -------------------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK", 200


# -------------------------
#   Dispatcher
# -------------------------
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.document.mime_type("application/pdf"), handle_pdf))


# -------------------------
#   App Home
# -------------------------
@app.route("/")
def home():
    return "Bot Running!"


# -------------------------
#   Run Local (optional)
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)