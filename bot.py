import telebot
import pdfplumber
import google.generativeai as genai
from flask import Flask
import threading
import time

# ------------------------------
# YOUR KEYS
# ------------------------------
TELEGRAM_TOKEN = "8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k"
GEMINI_API_KEY = "AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8"
# ------------------------------

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Bot token or Gemini key missing!")

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Running ✓"

# ---------------------------------
# SAFE POLLING THREAD (NO 409)
# ---------------------------------
def safe_polling():
    time.sleep(2)
    print("Starting polling thread...")
    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=[]
    )

# ---------------------------------
# COMMAND: /start
# ---------------------------------
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,
    "PDF भेजो ❤️\nमैं उसको Gujarati MCQ Test HTML बना कर दे दूँगा 😍")

# ---------------------------------
# PDF TO TEST
# ---------------------------------
@bot.message_handler(content_types=['document'])
def pdf_handler(msg):

    # Download PDF
    file_id = msg.document.file_id
    file_info = bot.get_file(file_id)
    pdf_bytes = bot.download_file(file_info.file_path)

    with open("input.pdf", "wb") as f:
        f.write(pdf_bytes)

    # Extract text
    text = ""
    try:
        with pdfplumber.open("input.pdf") as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except:
        bot.reply_to(msg, "PDF पढ़ नहीं पाया 😭")
        return

    # Gemini prompt
    prompt = f"""
    नीचे PDF से निकाला गया टेक्स्ट है।
    इस टेक्स्ट से automatic MCQ questions detect करो
    और नीचे जैसा HTML quiz बनाओ:

    <html><body>
    <h2>Generated Quiz</h2>
    <div class='card'>
        <p>Q1: ...</p>
        <button>A</button>
        <button>B</button>
        <button>C</button>
        <button>D</button>
    </div>
    </body></html>

    TEXT:
    {text}
    """

    # Gemini generate
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        result = model.generate_content(prompt)
        html = result.text
    except Exception as e:
        bot.reply_to(msg, f"Gemini Error:\n{e}")
        return

    # Save HTML
    with open("quiz.html", "w", encoding="utf-8") as f:
        f.write(html)

    # Send file
    with open("quiz.html", "rb") as f:
        bot.send_document(msg.chat.id, f, caption="Your Quiz HTML ❤️")

    bot.reply_to(msg, "Test तैयार है ❤️")

# ---------------------------------
# RUN BOTH: Flask + Polling
# ---------------------------------
if __name__ == "__main__":
    threading.Thread(target=safe_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)