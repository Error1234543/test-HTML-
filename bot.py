
import telebot
import pdfplumber
import google.generativeai as genai
from flask import Flask
import threading

# -----------------------------------
# YOUR TOKENS HERE
# -----------------------------------
TELEGRAM_TOKEN = "8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k"
GEMINI_API_KEY = "AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8"
# -----------------------------------

if TELEGRAM_TOKEN.strip() == "" or GEMINI_API_KEY.strip() == "":
    raise ValueError("BOT TOKEN OR GEMINI KEY IS EMPTY!")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running successfully 😊"

def start_polling():
    print("BOT POLLING STARTED...")
    bot.infinity_polling(skip_pending=True)

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "PDF bhejo, main Gujarati MCQ test HTML bana dunga ❤️")

@bot.message_handler(content_types=['document'])
def handle_pdf(msg):
    file_id = msg.document.file_id
    file_info = bot.get_file(file_id)
    pdf_data = bot.download_file(file_info.file_path)

    with open("input.pdf", "wb") as f:
        f.write(pdf_data)

    # Extract text
    text = ""
    try:
        with pdfplumber.open("input.pdf") as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except:
        bot.reply_to(msg, "PDF read nahi hua 😭")
        return

    prompt = f"""
    Niche Gujarati / Hindi PDF text diya gaya hai.
    Is text ke MCQ detect kar ke ek clean HTML quiz banao.

    HTML FORMAT:
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

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        result = model.generate_content(prompt)
        html = result.text
    except Exception as e:
        bot.reply_to(msg, f"Gemini Error: {e}")
        return

    # Save file
    with open("quiz.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("quiz.html", "rb") as f:
        bot.send_document(msg.chat.id, f, caption="Your Quiz HTML ❤️")

    bot.reply_to(msg, "Test ready hai! ❤️")

# --------------------------------------------
# Run flask + bot together (for Render)
# --------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_polling).start()
    app.run(host="0.0.0.0", port=10000)