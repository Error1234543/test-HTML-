# bot.py
import os
import json
import time
import logging
from flask import Flask, request, jsonify
import requests
import pdfplumber
import google.generativeai as genai
import html as html_escape
import re

# ---- CONFIG ----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # recommended to set in Render env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # recommended to set in Render env

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("Please set TELEGRAM_TOKEN and GEMINI_API_KEY in environment variables")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)

# Try to pick a working model; fallback list
MODEL_CANDIDATES = [
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-pro",
    "models/gemini-1.5-flash-latest",
    "models/gemini-2.5-flash-latest",
]

def choose_working_model():
    try:
        available = genai.list_models()
        names = [m.name for m in available]
        for cand in MODEL_CANDIDATES:
            if cand in names:
                logging.info("Using model from list: %s", cand)
                return cand
        # fallback: return first available that mentions 'gemini' or 'flash'
        for n in names:
            if "gemini" in n:
                return n
        return names[0] if names else MODEL_CANDIDATES[0]
    except Exception as e:
        logging.warning("list_models failed: %s — falling back to default model candidate", e)
        # last resort
        return MODEL_CANDIDATES[0]

MODEL_NAME = choose_working_model()
logging.basicConfig(level=logging.INFO)
logging.info("Chosen Gemini model: %s", MODEL_NAME)

app = Flask(__name__)

# ---------- Helpers ----------
def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def send_document(chat_id, file_path, caption=None):
    url = f"{TELEGRAM_API}/sendDocument"
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
        for chunk in r.iter_content(1024*32):
            f.write(chunk)
    return local_path

# Basic MCQ parser (conservative): returns list of dicts {q: str, options: [..]}
def parse_mcqs_from_text(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    Q_REGEX = re.compile(r'^\s*(?:Q\.?\s*)?(\d{1,3})\s*[).:-]\s*(.*)', re.IGNORECASE)
    OPT_REGEX = re.compile(r'^\s*(?:\(?([A-D]|[1-4])\)?[).:-]|\b([A-D])\b\s*[:\-])\s*(.+)', re.IGNORECASE)
    questions = []
    cur = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = Q_REGEX.match(line)
        if m:
            if cur:
                questions.append(cur)
            cur = {"q": m.group(2).strip(), "options": []}
            i += 1
            # collect following lines - options or continuation
            while i < len(lines):
                nxt = lines[i]
                if Q_REGEX.match(nxt):
                    break
                om = OPT_REGEX.match(nxt)
                if om:
                    # capture option text
                    txt = om.group(3) if om.group(3) else (om.group(2) or om.group(1))
                    cur["options"].append(txt.strip())
                    i += 1
                    continue
                # if options already started and this line doesn't match option, append to last option
                if cur["options"]:
                    cur["options"][-1] += " " + nxt
                    i += 1
                    continue
                # else continuation of question
                cur["q"] += " " + nxt
                i += 1
            continue
        else:
            i += 1
            continue
    if cur:
        questions.append(cur)
    # Clean: only keep items with >=2 options
    clean = [q for q in questions if len(q.get("options", [])) >= 2 and len(q["q"])>3]
    return clean

# Use Gemini to find the correct answer for each question.
# We will send a prompt that includes a few Qs and ask for JSON answers.
def gemini_detect_answers(questions, model_name=MODEL_NAME):
    # Build small batch prompt (to avoid token explosion, do 10 at a time)
    answers = []
    batch_size = 8
    for start in range(0, len(questions), batch_size):
        batch = questions[start:start+batch_size]
        prompt_parts = []
        for idx, q in enumerate(batch, start=1):
            opts = q["options"]
            # label options as A/B/C/D
            labeled = "\n".join([f"{chr(65+i)}. {opts[i]}" for i in range(len(opts))])
            prompt_parts.append(f"Q{idx}. {q['q']}\n{labeled}\nAnswer (single letter):")
        prompt_text = "Here are multiple-choice questions. For each, return only the correct option letter (A/B/C/D) in a JSON array in order, like: [\"B\",\"A\",...].\n\n" + "\n\n".join(prompt_parts)
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt_text, max_output_tokens=512)
            text = resp.text.strip()
            # clean code fences
            text = text.replace("```json", "").replace("```", "").strip()
            # try parse as JSON
            try:
                js = json.loads(text)
            except:
                # fallback: extract letters using regex
                letters = re.findall(r'\b[A-D]\b', text.upper())
                if len(letters) >= len(batch):
                    js = letters[:len(batch)]
                else:
                    # try lines with letters
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    letters = []
                    for ln in lines:
                        m = re.match(r'^\s*([A-D])\b', ln.upper())
                        if m:
                            letters.append(m.group(1))
                    js = letters
            # append to answers
            for i, letter in enumerate(js):
                answers.append(letter if isinstance(letter, str) else str(letter))
        except Exception as e:
            logging.exception("Gemini batch error: %s", e)
            # fallback: empty answers for this batch
            for _ in batch:
                answers.append(None)
    # Map answers back to questions (as index)
    out = []
    for q, ans_letter in zip(questions, answers):
        if ans_letter and isinstance(ans_letter, str):
            # convert letter to index
            try:
                idx = ord(ans_letter.strip().upper()[0]) - 65
            except:
                idx = None
        else:
            idx = None
        out.append({"q": q["q"], "options": q["options"], "correctIndex": idx})
    return out

# Create final HTML from list of objects {q, options, correctIndex}
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
    html_template = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>{html_escape.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
body{{font-family:Arial,Helvetica,sans-serif;background:#0b1220;color:#e6eef6;padding:16px}}
.container{{max-width:900px;margin:0 auto}}
.card{{background:#071021;padding:16px;border-radius:8px}}
.q{{margin-bottom:12px;padding:12px;border-radius:8px;background:rgba(255,255,255,0.02)}}
.options{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.opt{{padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.04);cursor:pointer;text-align:left}}
.correct{{border-color:#10b981;background:rgba(16,185,129,0.08)}}
.wrong{{border-color:#ef4444;background:rgba(239,68,68,0.06)}}
.header{{display:flex;align-items:center;gap:12px}}
.small{{color:#94a3b8;font-size:13px}}
@media(max-width:600px){{.options{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="container">
  <div class="card header">
    <div>
      <h1>{html_escape.escape(title)}</h1>
      <div class="small">Generated: {now}</div>
    </div>
    <div style="margin-left:auto">
      Time (mins): <input id="mins" type="number" value="{minutes}" style="width:70px;padding:6px;border-radius:6px;border:none"/>
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
const questions = {js_data};

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
</html>
"""
    return html_template

# ---- Flask routes ----
@app.route("/", methods=["GET"])
def index():
    return "PDF→MCQ Bot (webhook) is running"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    logging.info("Received update")
    try:
        # Handle message with document (PDF)
        if "message" in update and "document" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            doc = update["message"]["document"]
            mime = doc.get("mime_type","")
            if "pdf" not in mime and not doc.get("file_name","").lower().endswith(".pdf"):
                send_message(chat_id, "Please send a PDF document.")
                return jsonify(ok=True)

            # get file path
            file_info = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": doc["file_id"]}).json()
            file_path = file_info["result"]["file_path"]
            local_pdf = "/tmp/input.pdf"
            download_file("/" + file_path, local_pdf)

            send_message(chat_id, "PDF received — extracting text (may take a moment)...")

            # extract text
            text = ""
            try:
                with pdfplumber.open(local_pdf) as pdf:
                    for p in pdf.pages:
                        t = p.extract_text()
                        if t:
                            text += t + "\n"
            except Exception as e:
                logging.exception("pdfplumber failed: %s", e)
                send_message(chat_id, "Failed to read PDF. If it's scanned image, try sending a text PDF or enable OCR.")
                return jsonify(ok=True)

            send_message(chat_id, "Parsing MCQs from PDF...")
            parsed = parse_mcqs_from_text(text)
            if not parsed:
                send_message(chat_id, "No MCQ-style questions detected automatically. If PDF contains an answer key or different format, try a clearer PDF.")
                return jsonify(ok=True)

            send_message(chat_id, f"Detected {len(parsed)} questions. Asking Gemini to find answers...")

            mcq_with_answers = gemini_detect_answers(parsed, model_name=MODEL_NAME)

            send_message(chat_id, "Generating HTML test...")
            html_content = build_html(mcq_with_answers, title=doc.get("file_name","Test"))

            out_path = "/tmp/test_quiz.html"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            send_document(chat_id, out_path, caption="Your interactive HTML test — open in Chrome for best experience.")
            send_message(chat_id, "Done — HTML test sent. Open it in browser to take the test.")

        else:
            # not a document — reply helpful message
            if "message" in update and "text" in update["message"]:
                chat_id = update["message"]["chat"]["id"]
                txt = update["message"]["text"].strip().lower()
                if txt in ("/start","start"):
                    send_message(chat_id, "Send me a PDF (Gujarati/Hindi/English). I will extract MCQs, ask Gemini to find the answers, and return an interactive HTML test.")
                else:
                    send_message(chat_id, "Send a PDF file to generate a test (supports Gujarati/Hindi/English MCQs).")
    except Exception as e:
        logging.exception("webhook handling failed: %s", e)
    return jsonify(ok=True)

# ---- To set webhook (run once locally / curl) ----
# Example:
# curl -F "url=https://<your-render-domain>/webhook" https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook

if __name__ == "__main__":
    # debug server (gunicorn will be used in Render)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)