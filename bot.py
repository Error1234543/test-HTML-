
import telebot
import pdfplumber
import google.generativeai as genai
import html
import re

# ---------------------------------------
# 🔑 YOUR KEYS HERE
# ---------------------------------------
TELEGRAM_TOKEN = "8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k"
GEMINI_KEY="AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8"

# ---------------------------------------
# CONFIG
# ---------------------------------------
bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_KEY)

MODEL = "models/gemini-1.5-flash"   # ⭐ NEVER FAILS


# =========== PDF → TEXT ===========
def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            text += p.extract_text() + "\n"
    return text


# =========== ANSWER FINDER (Gemini) ===========
def find_answers_with_gemini(text):
    prompt = f"""
You are an expert NEET MCQ solver.

PDF questions are in Gujarati or Hindi.
Extract all MCQs and return in JSON:

[
 { "question": "...", "options": ["A","B","C","D"], "answer": "B" }
]

ONLY return JSON, nothing else.

PDF content:
{text}
"""

    response = genai.GenerativeModel(MODEL).generate_content(prompt)
    return response.text


# =========== HTML TEST GENERATOR ===========
def generate_html_test(mcq_json):
    html_code = """
<!DOCTYPE html>
<html>
<head>
<title>MCQ Test</title>
<style>
body{font-family:Arial;margin:20px;}
.q{margin-bottom:20px;padding:10px;border:1px solid #aaa;border-radius:5px;}
button{padding:10px;margin-top:10px;}
</style>
</head>
<body>
<h2>Generated Test</h2>
<div id="test"></div>
<button onclick="finish()">Finish Test</button>
<script>
let data = REPLACE_DATA;
let html = "";
let userAns = [];

data.forEach((q,i)=>{
    html += `<div class='q'>
    <b>${i+1}) ${q.question}</b><br>`;
    q.options.forEach((op,j)=>{
        html += `<input type='radio' name='q${i}' value='${op}'> ${op}<br>`;
    });
    html += `</div>`;
});
document.getElementById("test").innerHTML = html;

function finish(){
    let correct = 0;
    data.forEach((q,i)=>{
        let marked = document.querySelector(`input[name='q${i}']:checked`);
        if(marked && marked.value == q.answer) correct++;
    });
    alert("Your Score: "+correct+" / "+data.length);
}
</script>
</body>
</html>
"""

    return html_code.replace("REPLACE_DATA", mcq_json)


# =========== TELEGRAM HANDLER ===========
@bot.message_handler(content_types=['document'])
def pdf_handler(message):
    try:
        file = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file.file_path)

        path = "input.pdf"
        with open(path, "wb") as f:
            f.write(downloaded)

        bot.reply_to(message, "📄 PDF received… extracting text…")

        text = extract_text_from_pdf(path)

        bot.reply_to(message, "🤖 Finding answers using Gemini…")

        mcq_json = find_answers_with_gemini(text)

        bot.reply_to(message, "🛠 Generating HTML test…")

        html_data = generate_html_test(mcq_json)

        with open("test.html", "w", encoding="utf-8") as f:
            f.write(html_data)

        with open("test.html", "rb") as f:
            bot.send_document(message.chat.id, f, caption="✔ Your Test Ready!")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# =============================
# RUN BOT (NO 409 ERROR)
# =============================
bot.infinity_polling(skip_pending=True)