import os
import telebot
from google.cloud import vision
import google.generativeai as genai
import json

# Load keys
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

bot = telebot.TeleBot(TOKEN)

# Google Vision OCR
def extract_text_from_pdf(path):
    client = vision.ImageAnnotatorClient()
    with open(path, "rb") as f:
        content = f.read()

    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(response.error.message)

    return response.full_text_annotation.text


# Gemini MCQ Detector
genai.configure(api_key=GEMINI_KEY)

def detect_mcqs_from_text(text):
    prompt = f"""
    Gujarati NEET/JEE test PDF text:

    {text}

    Extract MCQs EXACTLY.
    OPTIONS and QUESTIONS must remain in Gujarati.
    RETURN STRICT JSON ONLY:

    {{
        "questions":[
            {{
                "q":"question text",
                "options":["Option A","Option B","Option C","Option D"],
                "answer":"A"
            }}
        ]
    }}
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    res = model.generate_content(prompt)

    try:
        return json.loads(res.text)
    except:
        return {"questions": []}


# HTML generator (Pro Level AKDM)
def generate_html(data):
    html = """
    <html><head><meta charset='UTF-8'>
    <style>
    body{font-family:Arial;margin:20px;background:#f8f8f8;}
    .box{background:white;padding:15px;border-radius:12px;margin-bottom:15px;box-shadow:0 2px 5px rgba(0,0,0,0.1);}
    .q{font-weight:bold;font-size:18px;color:#222;}
    .opt{margin-left:20px;}
    .ans{color:green;font-weight:bold;}
    </style></head><body>
    """

    for i, q in enumerate(data["questions"], 1):
        html += f"""
        <div class="box">
            <p class="q">Q{i}. {q['q']}</p>
            <div class="opt">
                <ol>
                    {''.join([f'<li>{o}</li>' for o in q['options']])}
                </ol>
            </div>
            <p class='ans'>Answer: {q['answer']}</p>
        </div>
        """

    html += "</body></html>"
    return html


# Telegram handlers
@bot.message_handler(commands=['html'])
def ask_pdf(message):
    bot.reply_to(message, "📄 Send your NEET/JEE Gujarati PDF to convert into PRO-level HTML Quiz.")

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    file_path = f"/tmp/{message.document.file_name}"
    with open(file_path, "wb") as f:
        f.write(downloaded)

    bot.reply_to(message, "🔍 Scanning Gujarati PDF…")

    text = extract_text_from_pdf(file_path)
    bot.reply_to(message, "🤖 Extracting MCQs using Gemini…")

    mcqs = detect_mcqs_from_text(text)
    html = generate_html(mcqs)

    output = file_path.replace(".pdf", ".html")
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    bot.send_document(message.chat.id, open(output, "rb"))


print("BOT RUNNING…")
bot.polling()