import telebot
import pdfplumber
import google.generativeai as genai
from flask import Flask
import threading

TELEGRAM_TOKEN = "8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k"
GEMINI_API_KEY = "AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot running OK"

def start_polling():
    bot.infinity_polling(skip_pending=True)

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "PDF bhejo, test HTML bana dunga ❤️")

@bot.message_handler(content_types=['document'])
def handle_pdf(msg):
    file_id = msg.document.file_id
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)

    with open("temp.pdf", "wb") as f:
        f.write(downloaded)

    text = ""
    with pdfplumber.open("temp.pdf") as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    prompt = f"""
    Gujarati PDF text niche diya gaya hai.
    Tumne us text ke MCQ automatically detect karke
    ek clean HTML quiz banana hai.

    HTML format:
    <html><body>
    <h2>Test</h2>
    <div class='q'>
        <p>Q1 ...</p>
        <button>A</button>
        <button>B</button>
        <button>C</button>
        <button>D</button>
    </div>
    </body></html>

    TEXT:
    {text}
    """

    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    out = model.generate_content(prompt)

    html = out.text

    with open("quiz.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("quiz.html", "rb") as f:
        bot.send_document(msg.chat.id, f)

    bot.reply_to(msg, "Your quiz is ready ❤️")

if __name__ == "__main__":
    threading.Thread(target=start_polling).start()
    app.run(host="0.0.0.0", port=int(10000))