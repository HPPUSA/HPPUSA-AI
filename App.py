
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
<footer>HPPUSA · Human ideas. AI-powered tools. Real value.</footer>
<script>
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
    reply.textContent = data.reply || data.error || 'Please try again.';
    chat.appendChild(reply);
  } catch (error) {
    status.textContent = 'Could not connect. Please try again.';
  } finally {
    button.disabled = false;
    status.textContent = '';
    chat.scrollTop = chat.scrollHeight;
  }
}
document.getElementById('question').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
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
                        "You are HPPUSA AI, a friendly and practical home "
                        "management assistant. Help homeowners with maintenance, "
                        "repairs, budgeting, warranties, property records, "
                        "organization, and planning. Give clear step-by-step "
                        "answers that are easy for a homeowner to understand. "
                        "When a question involves safety, electrical work, "
                        "plumbing, structural issues, or other potentially "
                        "dangerous work, recommend using a qualified professional "
                        "when appropriate. Do not claim to be a licensed contractor "
                        "or professional. Keep answers useful and reasonably concise."
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
        print("Groq error:", error)
        return jsonify({
            "error": "HPPUSA AI could not complete the request right now. Please try again."
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

