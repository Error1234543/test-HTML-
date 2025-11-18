import telebot
import pdfplumber
import google.generativeai as genai
import time
import os

# -------------------------------
# 🔑 SET YOUR TOKENS HERE
# -------------------------------
TELEGRAM_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# Use stable model
model = genai.GenerativeModel("models/gemini-2.0-flash")

# -------------------------------
# PDF → TEXT
# -------------------------------
def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# -------------------------------
# Generate HTML TEST
# -------------------------------
def generate_test_html(questions):
    html = """
<html>
<head>
<title>Test</title>
<style>
body{font-family:Arial;background:#f2f2f2;padding:20px;}
.card{background:#fff;padding:15px;margin:10px;border-radius:10px;box-shadow:0 0 5px #aaa;}
.btn{padding:10px 20px;background:#007bff;color:#fff;border:none;border-radius:5px;}
</style>
<script>
let index = 0;
let correct = 0;
let data = QUESTIONS;

function showQ(){
    if(index >= data.length){
        document.body.innerHTML = "<h2>Test Finished!</h2><h3>Score: "+correct+" / "+data.length+"</h3>";
        return;
    }
    let q = data[index];
    let html = "<div class='card'><b>Q"+(index+1)+".</b> "+q.q+"<br><br>";
    for(let o of q.options){
        html += "<button class='btn' onclick='check(\""+o+"\")'>"+o+"</button><br><br>";
    }
    html += "</div>";
    document.body.innerHTML = html;
}

function check(option){
    if(option === data[index].ans){ correct++; }
    index++;
    showQ();
}
window.onload = showQ;
</script>
</head>
<body>
</body>
</html>
"""
    # Insert actual JSON questions
    import json
    return html.replace("QUESTIONS", json.dumps(questions))


# -------------------------------
# Gemini: Create Test Questions
# -------------------------------
def create_mcq(text):
    prompt = f"""
You are an expert Gujarati teacher.
Convert the following PDF content into EXACT MCQ format.

Rules:
- All questions in Gujarati only
- Each question must have 4 options
- Give correct answer
- Return in this JSON format only:
[
  {{"q":"question", "options":["A","B","C","D"], "ans":"A"}}
]

CONTENT:
{text}
"""

    resp = model.generate_content(prompt)
    import json

    try:
        data = json.loads(resp.text)
    except:
        # Gemini kabhi kabhi code block deta hai → clean
        cleaned = resp.text.replace("```json", "").replace("```", "")
        data = json.loads(cleaned)

    return data


# -------------------------------
# On PDF Upload
# -------------------------------
@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    file = bot.get_file(message.document.file_id)
    path = f"{message.document.file_id}.pdf"
    downloaded = bot.download_file(file.file_path)

    with open(path, "wb") as f:
        f.write(downloaded)

    bot.reply_to(message, "📥 PDF received!\n⏳ Extracting text...")

    text = extract_text_from_pdf(path)

    bot.reply_to(message, "🧠 Creating MCQ Test using Gemini... Wait...")

    questions = create_mcq(text)

    bot.reply_to(message, f"✔️ {len(questions)} questions generated!")

    html = generate_test_html(questions)

    html_file = "test.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    # Send file
    with open(html_file, "rb") as f:
        bot.send_document(message.chat.id, f, caption="🎉 Your Test is Ready!")

# -------------------------------
# START
# -------------------------------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Send me a PDF in Gujarati and I will create a full MCQ TEST HTML for you!")

print("BOT STARTED...")
bot.infinity_polling()