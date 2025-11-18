import telebot
import pdfplumber
import html
import json
import google.generativeai as genai
from datetime import datetime
from flask import Flask

# ------------------------------------------------------
# TOKENS (set here, no Render env needed)
# ------------------------------------------------------
TELEGRAM_TOKEN = "8170315201:AAFG-m59j0-yxn02ZSxXjAYqR8fJt5OJJ_k"
GEMINI_API_KEY = "AIzaSyB5TA6nDIj8VARsC4LPfdxu7_HBnetmPg8"

# ------------------------------------------------------
# TELEGRAM + GEMINI SETUP
# ------------------------------------------------------
bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ------------------------------------------------------
# DUMMY FLASK APP FOR RENDER (keeps port open)
# ------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Telegram MCQ Bot Running Successfully!"

# ------------------------------------------------------
# PDF EXTRACTOR
# ------------------------------------------------------
def extract_pdf_text(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            try:
                pages.append(p.extract_text() or "")
            except:
                pages.append("")
    return "\n\n".join(pages)

# ------------------------------------------------------
# GEMINI MCQ PARSER
# ------------------------------------------------------
def parse_mcqs_with_gemini(text):
    prompt = """
Extract all MCQ questions from this Gujarati/Hindi text.
Return ONLY JSON:
[
 {"qno":1, "question":"...", "options":["A","B","C","D"], "correct":2}
]
TEXT:
""" + text

    response = model.generate_content(prompt)
    output = response.text.strip().replace("```json","").replace("```","")

    try:
        return json.loads(output)
    except:
        import re
        match = re.search(r'\[.*\]', output, re.S)
        if match:
            return json.loads(match.group())
        return []

# ------------------------------------------------------
# HTML TEST GENERATOR
# ------------------------------------------------------
def generate_html(mcqs, title):

    safe = []
    for q in mcqs:
        safe.append({
            "text": html.escape(q["question"]),
            "choices": [html.escape(c) for c in q["options"]],
            "correctIndex": int(q["correct"])
        })

    js_array = json.dumps(safe, ensure_ascii=False)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html_code = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>""" + title + """</title>
<style>
body{font-family:Arial;background:#0d1117;color:white;padding:15px}
.card{background:#111827;padding:15px;border-radius:10px;margin-top:10px}
.opt{padding:10px;border:1px solid #333;border-radius:6px;margin-top:6px;cursor:pointer}
.correct{background:#065f46}
.wrong{background:#7f1d1d}
</style>
</head>
<body>

<h2>""" + title + """</h2>
<p>Generated at: """ + now + """</p>

<div id="test"></div>
<button onclick="finishTest()">Finish</button>

<div id="result" class="card" style="display:none"></div>

<script>
let questions = """ + js_array + """;
let ans = Array(questions.length).fill(null);

function render() {
    let html = "";
    questions.forEach((q,i)=>{
        html += `<div class='card'><b>Q${i+1}.</b> ${q.text}<br>`;
        q.choices.forEach((c,j)=>{
            html += `<div class='opt' onclick='selectOpt(${i},${j},this)'>${String.fromCharCode(65+j)}. ${c}</div>`;
        });
        html += "</div>";
    });
    document.getElementById("test").innerHTML = html;
}

function selectOpt(qn,on,el){
    if(ans[qn] !== null) return;
    ans[qn] = on;
    let parent = el.parentNode;
    [...parent.children].forEach((x,idx)=>{
        x.style.pointerEvents = "none";
        if(idx === questions[qn].correctIndex) x.classList.add("correct");
        else if(idx === on) x.classList.add("wrong");
    });
}

function finishTest(){
    let right = 0;
    ans.forEach((a,i)=>{ if(a === questions[i].correctIndex) right++; });

    let out = `<h3>Result</h3>
               <p>Score: ${right} / ${questions.length}</p><hr>`;

    questions.forEach((q,i)=>{
        if(ans[i] !== q.correctIndex){
            out += `<p><b>Q${i+1}:</b> ${q.text}<br>
                    Your: ${ans[i]===null? "Not answered" : q.choices[ans[i]]}<br>
                    Correct: ${q.choices[q.correctIndex]}</p><hr>`;
        }
    });

    document.getElementById("result").style.display="block";
    document.getElementById("result").innerHTML = out;
}

render();
</script>

</body>
</html>
"""
    return html_code

# ------------------------------------------------------
# TELEGRAM BOT HANDLERS
# ------------------------------------------------------
@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "Send Gujarati/Hindi PDF.\nI'll generate MCQ Test HTML using Gemini AI 🤖")

@bot.message_handler(content_types=['document'])
def pdf_handler(m):
    try:
        file_info = bot.get_file(m.document.file_id)
        raw = bot.download_file(file_info.file_path)

        path = "/tmp/in.pdf"
        with open(path, "wb") as f:
            f.write(raw)

        bot.reply_to(m, "Extracting PDF…")

        text = extract_pdf_text(path)
        bot.send_message(m.chat.id, "Detecting MCQs using Gemini AI…")

        mcqs = parse_mcqs_with_gemini(text)
        if not mcqs:
            bot.reply_to(m.chat.id, "❌ No MCQs found.")
            return

        bot.send_message(m.chat.id, "✔ MCQs detected.\nGenerating HTML Test…")

        title = (m.document.file_name or "Test").replace(".pdf","")
        html_file = generate_html(mcqs, title)

        output = "/tmp/test.html"
        with open(output, "w", encoding="utf-8") as f:
            f.write(html_file)

        bot.send_document(m.chat.id, open(output, "rb"), caption="Your HTML Test is Ready ✔")

    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

# ------------------------------------------------------
# RUN EVERYTHING
# ------------------------------------------------------
import threading

def run_bot():
    bot.infinity_polling()

threading.Thread(target=run_bot).start()

# Flask server for Render
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)