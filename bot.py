import telebot
import pdfplumber
import google.generativeai as genai
from flask import Flask
import threading

# ------------------------------
# ADD YOUR TOKENS HERE
# ------------------------------
TELEGRAM_TOKEN = "8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k"
GEMINI_API_KEY = "AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8"
# ------------------------------

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Token or API key missing!")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running OK ✓"

def start_polling():
    bot.infinity_polling(skip_pending=True)

# ------------------------------
# Start command
# ------------------------------
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "PDF भेजो → मैं उसको Gujarati MCQ Test HTML में बदल दूँगा ❤️")

# ------------------------------
# PDF Handler
# ------------------------------
@bot.message_handler(content_types=['document'])
def handle_pdf(msg):
    file_id = msg.document.file_id
    file_info = bot.get_file(file_id)
    data = bot.download_file(file_info.file_path)

    with open("file.pdf", "wb") as f:
        f.write(data)

    text = ""
    try:
        with pdfplumber.open("file.pdf") as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except:
        bot.reply_to(msg, "PDF पढ़ नहीं पाया 😭")
        return

    prompt = f"""
    नीचे दिया गया टेक्स्ट Gujarati / Hindi PDF से निकाला गया है।
    इसका automatic MCQ Quiz HTML फॉर्मेट बनाओ।

    HTML FORMAT EXACT LIKE THIS:
    <html><body>
    <h2>Generated Quiz</h2>
    <div class='q'>
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
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        result = model.generate_content(prompt)
        html = result.text
    except Exception as e:
        bot.reply_to(msg, f"Gemini Error: {e}")
        return

    # Save HTML file
    with open("quiz.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("quiz.html", "rb") as f:
        bot.send_document(msg.chat.id, f, caption="Your HTML Quiz ❤️")

    bot.reply_to(msg, "Test तैयार है! ❤️")

# ------------------------------
# Run both Flask + Telegram Polling
# ------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_polling).start()
    app.run(host="0.0.0.0", port=10000)