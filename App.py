
import os
from flask import Flask, request, jsonify, render_template_string
from groq import Groq
app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HPPUSA AI | Home Assistant</title>
<style>
body {
  margin: 0; font-family: Arial, sans-serif;
  background: #f3f6fb; color: #17243a;
}
header {
  background: #102747; color: white; text-align: center;
  padding: 28px 16px; border-bottom: 4px solid #c9a44c;
}
header h1 { margin: 0 0 8px; }
header p { margin: 0; }
main {
  max-width: 720px; margin: 28px auto; padding: 20px;
}
.panel {
  background: white; border-radius: 14px;
  padding: 22px; box-shadow: 0 3px 14px #0001;
}
#chat {
  min-height: 200px; max-height: 360px;
  overflow-y: auto; margin-bottom: 16px;
}
.message {
  padding: 12px; border-radius: 10px;
  margin: 10px 0; white-space: pre-wrap;
}
.bot { background: #edf2f8; }
.user { background: #e4ecfb; text-align: right; }
textarea {
  width: 100%; box-sizing: border-box; padding: 12px;
  border: 1px solid #cbd4e0; border-radius: 8px;
  font: inherit; resize: vertical;
}
button {
  background: #102747; color: white; border: 0;
  border-radius: 8px; padding: 12px 18px;
  margin-top: 10px; font-size: 16px; cursor: pointer;
}
button:disabled { opacity: .6; }
footer { text-align: center; color: #68758a; padding: 20px; }
</style>
</head>
<body>
<header>
  <h1>HPPUSA AI</h1>
  <p>Your intelligent home management assistant</p>
</header>
<main>
  <div class="panel">
    <h2>How can I help with your home?</h2>
    <p>Ask about maintenance, repairs, budgets, warranties, or organizing your property.</p>
    <div id="chat" aria-live="polite">
      <div class="message bot">Welcome to HPPUSA AI! Tell me what you need help with, and we'll take it one step at a time.</div>
    </div>
    <textarea id="question" rows="3" placeholder="For example: Help me create a home maintenance checklist"></textarea>
    <button id="send" onclick="sendMessage()">Send message</button>
    <p id="status" role="status"></p>
  </div>
</main>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js"></script>
<script>
marked.setOptions({
  gfm: true,
  breaks: true
});

function formatReply(text) {
  const cleaned = String(text)
    .replace(/&#x20;/gi, ' ')
    .replace(/&#32;/gi, ' ')
    .replace(/&#91;/gi, '[')
    .replace(/&#93;/gi, ']');

  const html = marked.parse(cleaned);
  return DOMPurify.sanitize(html);
}
async function sendMessage() {
  const input = document.getElementById('question');
  const chat = document.getElementById('chat');
  const status = document.getElementById('status');
  const button = document.getElementById('send');
  const question = input.value.trim();

  if (!question) {
    status.textContent = 'Please enter a question first.';
    return;
  }

  const userMessage = document.createElement('div');
  userMessage.className = 'message user';
  userMessage.textContent = question;
  chat.appendChild(userMessage);

  input.value = '';
  button.disabled = true;
  status.textContent = 'Preparing your response...';

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: question})
    });

    const data = await response.json();
    const reply = document.createElement('div');
    reply.className = 'message bot';

    const replyText =
      data.reply || data.error || 'Please try again.';

    reply.innerHTML = formatReply(replyText);
    chat.appendChild(reply);

  } catch (error) {
    status.textContent = 'Could not connect. Please try again.';
  } finally {
    button.disabled = false;
    if (!status.textContent.startsWith('Could not connect')) {
      status.textContent = '';
    }
    chat.scrollTop = chat.scrollHeight;
  }
}

document.getElementById('question').addEventListener(
  'keydown',
  function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
);
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(PAGE)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Please enter a question."}), 400

    if len(message) > 3000:
        return jsonify({"error": "Please keep your question under 3,000 characters."}), 400

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return jsonify({
            "error": "HPPUSA AI is not connected to its AI service yet."
        }), 500

    try:
        client = Groq(api_key=api_key)

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are HPPUSA AI, a friendly, professional home "
                        "management assistant. Help homeowners with maintenance, "
                        "repairs, budgets, warranties, property records, and planning. "

                        "Make every answer practical, accurate, and easy to follow. "
                        "Use a short, descriptive heading when helpful. Use numbered "
                        "steps for instructions and bullet lists for checklists. "
                        "Explain unfamiliar terms in plain English. Include realistic "
                        "examples when they help the homeowner take action. "

                        "When appropriate, finish with a clear next step or a short "
                        "checklist. Keep simple answers brief and give more detail "
                        "when the question requires it. Do not repeat information "
                        "unnecessarily. Never invent prices, facts, or guarantees. "
                        "For home repairs, prioritize safety over completing the repair. For plumbing leaks, advise "
                        "the homeowner to shut off the appropriate water supply if safe, contain the "
                        "water, and protect people and property from further damage. Never recommend "
                        "tightening, loosening, disassembling, or attempting to repair a leaking plumbing "
                        "connection as a default troubleshooting step. Never recommend turning the water "
                        "back on to test a connection that is leaking or may still be leaking. Do not "
                        "suggest repeated tightening or repeated testing. Explain that the correct repair "
                        "depends on the type and condition of the fitting and may require a qualified "
                        "plumber. Recommend a qualified plumber if the leak continues, the source is "
                        "unclear, a fitting appears damaged or corroded, or the homeowner is unsure how "
                        "to proceed. If water is near outlets, wiring, or electrical equipment, warn the "
                        "homeowner not to touch wet equipment or enter standing water where electrical "
                        "hazards may exist. Encourage documenting the problem without taking risks. "
                        "For electrical work, gas, structural problems, major plumbing, or other "
                        "potentially dangerous tasks, explain the risks and recommend a qualified "
                        "professional when appropriate. Do not claim to be a licensed contractor or "
                        "other licensed professional. Be respectful, patient, and encouraging. Help "
                        "homeowners take one manageable step at a time. "
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            temperature=0.6,
            max_completion_tokens=2048,
            stream=False
        )

        reply = completion.choices[0].message.content
        return jsonify({"reply": reply})

    except Exception as error:
        print("Groq error:", repr(error), flush=True)
        print("Groq error type:", type(error).__name__, flush=True)
        print("Groq error cause:", repr(error.__cause__), flush=True)
        return jsonify({
            "error": "HPPUSA AI could not complete the request right now. Please try again."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


