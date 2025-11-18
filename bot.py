# bot.py
import os
import json
import time
import logging
import re
from flask import Flask, request, jsonify
import requests
import pdfplumber
import google.generativeai as genai
import html as html_escape

# -------- CONFIG - use Render Environment variables (recommended) ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or ""
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("Please set TELEGRAM_TOKEN and GEMINI_API_KEY environment variables.")

TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_TOKEN
FILE_API = "https://api.telegram.org/file/bot" + TELEGRAM_TOKEN

# ---------- GenAI setup ----------
genai.configure(api_key=GEMINI_API_KEY)

# Candidate models; we'll pick one that is available for your key.
MODEL_CANDIDATES = [
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-flash-latest"
]

def choose_model():
    try:
        models = genai.list_models()
        names = [m.name for m in models]
        for c in MODEL_CANDIDATES:
            if c in names:
                logging.info("Using model: %s", c)
                return c
        # fallback: first gemini-like
        for n in names:
            if "gemini" in n:
                return n
        return MODEL_CANDIDATES[0]
    except Exception as e:
        logging.warning("list_models failed: %s — will fallback to %s", e, MODEL_CANDIDATES[0])
        return MODEL_CANDIDATES[0]

MODEL_NAME = choose_model()
logging.basicConfig(level=logging.INFO)
logging.info("Chosen model: %s", MODEL_NAME)

app = Flask(__name__)

# -------- helpers to talk to Telegram ----------
def send_message(chat_id, text):
    requests.post(TELEGRAM_API + "/sendMessage", json={"chat_id": chat_id, "text": text})

def send_document(chat_id, file_path, caption=None):
    url = TELEGRAM_API + "/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        r = requests.post(url, data=data, files=files)
        return r

def download_file(file_path_on_telegram, local_path):
    url = FILE_API + file_path_on_telegram
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(local_path, "wb") as f:
        for chunk in r.iter_content(32768):
            f.write(chunk)
    return local_path

# -------- basic MCQ parser (conservative) ----------
def parse_mcqs_from_text(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    Q_REGEX = re.compile(r'^\s*(?:Q\.?\s*)?(\d{1,3})[\).\:-]\s*(.*)', re.IGNORECASE)
    OPT_REGEX = re.compile(r'^\s*(?:\(?([A-D]|[1-4])\)?[\).\:-]?)\s*(.+)', re.IGNORECASE)
    questions = []
    i = 0
    cur = None
    while i < len(lines):
        line = lines[i]
        m = Q_REGEX.match(line)
        if m:
            if cur:
                questions.append(cur)
            cur = {"q": m.group(2).strip(), "options": []}
            i += 1
            # collect options and continued lines
            while i < len(lines):
                nxt = lines[i]
                if Q_REGEX.match(nxt):
                    break
                om = OPT_REGEX.match(nxt)
                if om:
                    # option text
                    txt = om.group(2).strip() if om.group(2) else om.group(1).strip()
                    cur["options"].append(txt)
                    i += 1
                    continue
                if cur["options"]:
                    # continuation of last option
                    cur["options"][-1] += " " + nxt
                    i += 1
                    continue
                # continuation of question text
                cur["q"] += " " + nxt
                i += 1
            continue
        else:
            i += 1
    if cur:
        questions.append(cur)
    # keep only items with >=2 options and reasonable question length
    clean = [q for q in questions if len(q.get("options", [])) >= 2 and len(q["q"]) > 3]
    return clean

# -------- use Gemini only to detect answers ----------
def gemini_detect_answers(questions, model_name=MODEL_NAME):
    answers = []
    batch_size = 8
    for start in range(0, len(questions), batch_size):
        batch = questions[start:start+batch_size]
        prompt_parts = []
        for idx, q in enumerate(batch, start=1):
            opts = q["options"]
            labeled = "\n".join([f"{chr(65+i)}. {opts[i]}" for i in range(len(opts))])
            prompt_parts.append(f"Q{idx}. {q['q']}\n{labeled}\nAnswer (single letter):")
        prompt_text = "For these multiple-choice questions, return a JSON array of correct option letters (A/B/C/D) in order, e.g. [\"B\",\"A\",...].\n\n" + "\n\n".join(prompt_parts)
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt_text, max_output_tokens=512)
            text = resp.text.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            try:
                js = json.loads(text)
            except:
                # fallback: extract single letters
                letters = re.findall(r'\b[A-D]\b', text.upper())
                if len(letters) >= len(batch):
                    js = letters[:len(batch)]
                else:
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    letters = []
                    for ln in lines:
                        m = re.match(r'^([A-D])', ln.upper())
                        if m:
                            letters.append(m.group(1))
                    js = letters
            for letter in js:
                answers.append(letter if isinstance(letter, str) else str(letter))
        except Exception as e:
            logging.exception("Gemini batch error: %s", e)
            for _ in batch:
                answers.append(None)
    # map to questions
    out = []
    for q, ans_letter in zip(questions, answers):
        if ans_letter and isinstance(ans_letter, str):
            try:
                idx = ord(ans_letter.strip().upper()[0]) - 65
            except:
                idx = None
        else:
            idx = None
        out.append({"q": q["q"], "options": q["options"], "correctIndex": idx})
    return out

# -------- HTML builder (no f-strings with braces) ----------
def build_html(mcq_list, title="Generated Test", minutes=20):
    safe_items = []
    for item in mcq_list:
        safe_items.append({
            "text": html_escape.escape(item["q"]),
            "choices": [html_escape.escape(c) for c in item["options"]],
            "correctIndex": item.get("correctIndex", None)
        })
    js_data = json.dumps(safe_items, ensure_ascii=False)
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    # Use placeholder %%QUESTIONS_JSON%% which we'll replace safely
    html_template = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>%%TITLE%%</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
body{font-family:Arial,Helvetica,sans-serif;background:#0b1220;color:#e6eef6;padding:16px}
.container{max-width:900px;margin:0 auto}
.card{background:#071021;padding:16px;border-radius:8px}
.q{margin-bottom:12px;padding:12px;border-radius:8px;background:rgba(255,255,255,0.02)}
.options{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.opt{padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.04);cursor:pointer;text-align:left}
.correct{border-color:#10b981;background:rgba(16,185,129,0.08)}
.wrong{border-color:#ef4444;background:rgba(239,68,68,0.06)}
.header{display:flex;align-items:center;gap:12px}
.small{color:#94a3b8;font-size:13px}
@media(max-width:600px){.options{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
  <div class="card header">
    <div>
      <h1>%%TITLE_ESCAPED%%</h1>
      <div class="small">Generated: %%NOW%%</div>
    </div>
    <div style="margin-left:auto">
      Time (mins): <input id="mins" type="number" value="%%MINUTES%%" style="width:70px;padding:6px;border-radius:6px;border:none"/>
      <button id="start">Start</button>
    </div>
  </div>

  <div id="quizWrap" class="card" style="margin-top:12px;display:none">
    <div id="quiz"></div>
    <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center">
      <div class="small">Timer: <span id="timer">00:00</span></div>
      <div><button id="finish">Finish</button></div>
    </div>
  </div>

  <div id="result" class="card" style="margin-top:12px;display:none"></div>
  <div class="small" style="margin-top:12px">Open in Chrome for best experience.</div>
</div>

<script>
const questions = %%QUESTIONS_JSON%%;
const quizEl = document.getElementById('quiz');
const quizWrap = document.getElementById('quizWrap');
const startBtn = document.getElementById('start');
const finishBtn = document.getElementById('finish');
const timerEl = document.getElementById('timer');
const resultEl = document.getElementById('result');
const minsInput = document.getElementById('mins');

let userAnswers = new Array(questions.length).fill(null);
let timerInterval = null;
let remaining = 0;

startBtn.addEventListener('click', ()=>{ 
  renderQuestions();
  quizWrap.style.display='block';
  resultEl.style.display='none';
  const mins = Math.max(1, Number(minsInput.value)||20);
  remaining = mins*60;
  timerEl.textContent = formatTime(remaining);
  clearInterval(timerInterval);
  timerInterval = setInterval(()=>{ remaining--; timerEl.textContent = formatTime(remaining); if(remaining<=0){ clearInterval(timerInterval); finishTest(); } },1000);
});

function formatTime(s){ const m = Math.floor(s/60), sec = s%60; return String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0'); }

function renderQuestions(){
  quizEl.innerHTML='';
  questions.forEach((q, idx)=>{
    const div = document.createElement('div'); div.className='q';
    div.innerHTML = '<strong>Q'+(idx+1)+'.</strong> ' + q.text;
    const opts = document.createElement('div'); opts.className='options';
    q.choices.forEach((c,i)=>{
      const b = document.createElement('button'); b.className='opt'; b.innerText = String.fromCharCode(65+i)+'. '+c;
      b.onclick = ()=>{ if(userAnswers[idx]!==null) return; userAnswers[idx]=i; // lock
        Array.from(opts.children).forEach((bb,ii)=>{ bb.disabled = true; if(ii===i) { if(ii===(q.correctIndex||-1)) bb.classList.add('correct'); else bb.classList.add('wrong') } if(ii===(q.correctIndex||-1)) bb.classList.add('correct'); });
      };
      opts.appendChild(b);
    });
    div.appendChild(opts);
    quizEl.appendChild(div);
  });
}

finishBtn.addEventListener('click', finishTest);

function finishTest(){
  clearInterval(timerInterval);
  resultEl.style.display='block';
  let attempted=0, correct=0;
  questions.forEach((q,i)=>{
    const ans = userAnswers[i];
    if(ans!==null){ attempted++; if(ans===(q.correctIndex||-1)) correct++;}
  });
  const total = questions.length;
  resultEl.innerHTML = '<h2>Result</h2><div>Attempted: '+attempted+' | Correct: '+correct+' | Score: '+Math.round((correct/total)*100)+'%</div>';
  let list = '<h3>Review</h3>';
  questions.forEach((q,i)=>{
    const ans = userAnswers[i];
    if(ans===null || ans!==(q.correctIndex||-1)){
      list += '<div><strong>Q'+(i+1)+'.</strong> '+q.text+'<br>Your: '+(ans===null?'<em>Not answered</em>':q.choices[ans])+'<br>Correct: '+( (q.correctIndex!==undefined && q.choices[q.correctIndex])? q.choices[q.correctIndex] : '<em>Not available</em>' )+'<hr></div>';
    }
  });
  resultEl.innerHTML += list;
  quizWrap.style.display='none';
}
</script>
</body>
</html>"""
    # safe replacements
    html_filled = html_template.replace("%%QUESTIONS_JSON%%", js_data)
    html_filled = html_filled.replace("%%TITLE%%", html_escape.escape(title))
    html_filled = html_filled.replace("%%TITLE_ESCAPED%%", html_escape.escape(title))
    html_filled = html_filled.replace("%%NOW%%", now)
    html_filled = html_filled.replace("%%MINUTES%%", str(minutes))
    return html_filled

# ---------- Flask webhook route ----------
@app.route("/", methods=["GET"])
def index():
    return "PDF → MCQ Webhook Bot (running)"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    try:
        if "message" in update and "document" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            doc = update["message"]["document"]
            mime = doc.get("mime_type","")
            if "pdf" not in mime and not doc.get("file_name","").lower().endswith(".pdf"):
                send_message(chat_id, "Please send a PDF.")
                return jsonify(ok=True)
            # get file path from telegram
            r = requests.get(TELEGRAM_API + "/getFile", params={"file_id": doc["file_id"]})
            r.raise_for_status()
            file_info = r.json()
            file_path = file_info["result"]["file_path"]
            local_pdf = "/tmp/input.pdf"
            download_file("/" + file_path, local_pdf)

            send_message(chat_id, "PDF received — extracting text (may take a moment)...")

            text = ""
            try:
                with pdfplumber.open(local_pdf) as pdf:
                    for p in pdf.pages:
                        t = p.extract_text()
                        if t:
                            text += t + "\n"
            except Exception as e:
                logging.exception("pdfplumber failed: %s", e)
                send_message(chat_id, "Failed to read PDF. If it's scanned image, use a text PDF or enable OCR.")
                return jsonify(ok=True)

            send_message(chat_id, "Parsing MCQs from PDF...")
            parsed = parse_mcqs_from_text(text)
            if not parsed:
                send_message(chat_id, "No MCQ-style questions detected automatically. Try a clearer PDF or include answer key.")
                return jsonify(ok=True)

            send_message(chat_id, f"Detected {len(parsed)} questions. Asking Gemini to find answers...")

            mcq_with_answers = gemini_detect_answers(parsed, model_name=MODEL_NAME)

            send_message(chat_id, "Generating interactive HTML test...")
            html_content = build_html(mcq_with_answers, title=doc.get("file_name","Generated Test"))

            out_path = "/tmp/test_quiz.html"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            send_document(chat_id, out_path, caption="Your interactive HTML test — open in Chrome for best experience.")
            send_message(chat_id, "Done — HTML test sent. Open it in browser to take the test.")
        else:
            # non-document messages
            if "message" in update and "text" in update["message"]:
                chat_id = update["message"]["chat"]["id"]
                txt = update["message"]["text"].strip().lower()
                if txt in ("/start","start"):
                    send_message(chat_id, "Send a PDF (Gujarati/Hindi/English). I'll extract MCQs, use Gemini to find answers and return an interactive HTML test.")
                else:
                    send_message(chat_id, "Send a PDF file to generate the test.")
    except Exception as e:
        logging.exception("webhook handling failed: %s", e)
    return jsonify(ok=True)

# ---- set webhook manually (run once) ----
# use this (replace <your-domain> and TELEGRAM_TOKEN):
# https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<your-render-domain>/webhook

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)