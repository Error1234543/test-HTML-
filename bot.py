import os
import telebot
import pdfplumber
import html
import json
import google.generativeai as genai
import re
from datetime import datetime

# --------------------
#   CONFIG
# --------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("ERROR: Please set TELEGRAM_TOKEN & GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

# --------------------
# PDF TEXT EXTRACTOR
# --------------------
def extract_pdf_text(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            try:
                pages.append(p.extract_text() or "")
            except:
                pages.append("")
    return "\n\n".join(pages)

# --------------------
# GEMINI → MCQ PARSER
# --------------------
def parse_mcqs_with_gemini(text, lang="gu"):
    prompt = f"""
Extract all MCQ questions from the following Gujarati/Hindi PDF text.

Output must be a JSON array ONLY, with objects like:
{{
  "qno": 1,
  "question": "text",
  "options": ["A","B","C","D"],
  "correct": 1
}}

Text:
{text}
"""
    response = model.generate_content(prompt)
    reply = response.text

    # clean for safety
    reply = reply.strip().replace("```json","").replace("```","")

    try:
        data = json.loads(reply)
        return data
    except:
        # fallback – try to fix list
        try:
            fixed = re.search(r'\[.*\]', reply, re.S)
            return json.loads(fixed.group())
        except:
            return []

# --------------------
# HTML GENERATOR
# --------------------
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

    html_code = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>
body{{font-family:Arial;background:#0d1117;color:white;padding:15px}}
.card{{background:#111827;padding:15px;border-radius:10px;margin-top:10px}}
.opt{{padding:10px;border:1px solid #333;border-radius:6px;margin-top:6px;cursor:pointer}}
.correct{{background:#065f46}}
.wrong{{background:#7f1d1d}}
</style>
</head>
<body>

<h2>{title}</h2>
<p>Generated at: {now}</p>

<div id="test" class="card"></div>
<button onclick="finishTest()">Finish</button>

<div id="result" class="card" style="display:none"></div>

<script>
let questions = {js_array};
let ans = Array(questions.length).fill(null);

function render(){
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

# --------------------
# BOT HANDLER
# --------------------
@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "Send any Gujarati PDF.\nI will auto-create an HTML MCQ test using Gemini AI.\nInclude word 'gujarati' in caption if needed.")

@bot.message_handler(content_types=['document'])
def pdf_handler(m):
    try:
        file_info = bot.get_file(m.document.file_id)
        raw = bot.download_file(file_info.file_path)

        local = "/tmp/input.pdf"
        with open(local,"wb") as f:
            f.write(raw)

        bot.reply_to(m,"PDF received ✔\nExtracting text…")

        text = extract_pdf_text(local)

        bot.send_message(m.chat.id,"Sending to Gemini AI… (MCQs + answers auto-detect)")

        mcqs = parse_mcqs_with_gemini(text)
        if not mcqs:
            bot.send_message(m.chat.id,"❌ No MCQ found. PDF may be scanned or unreadable.")
            return

        bot.send_message(m.chat.id,f"Found {len(mcqs)} MCQs ✔\nGenerating HTML test…")

        title = (m.document.file_name or "Test").replace(".pdf","")
        html_file = generate_html(mcqs, f"{title} – MCQ Test")

        out = "/tmp/test.html"
        with open(out,"w",encoding="utf-8") as f:
            f.write(html_file)

        bot.send_document(m.chat.id, open(out,"rb"), caption="Your MCQ Test HTML is ready ✔")

    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

print("Bot is running…")
bot.infinity_polling()
