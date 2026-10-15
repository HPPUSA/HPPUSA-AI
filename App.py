
import os
from flask import Flask, request, jsonify, render_template_string

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

    text = message.lower()

    if any(word in text for word in ["maintenance", "checklist", "seasonal"]):
        reply = (
            "Let's build your home maintenance checklist:\n"
            "1. Inspect smoke and carbon monoxide alarms.\n"
            "2. Check HVAC filters and service dates.\n"
            "3. Inspect for leaks around sinks, toilets, and windows.\n"
            "4. Check gutters, roof condition, and exterior drainage.\n"
            "5. Record each task, date, cost, and next due date.\n\n"
            "Adjust these tasks to your property and equipment."
        )
    elif any(word in text for word in ["budget", "expense", "cost", "spending"]):
        reply = (
            "Let's organize your home budget:\n"
            "1. List recurring bills and due dates.\n"
            "2. Record repair and maintenance expenses.\n"
            "3. Keep receipts and warranty information.\n"
            "4. Plan a reserve for unexpected repairs.\n\n"
            "Which home expenses would you like to organize first?"
        )
    elif any(word in text for word in ["warranty", "receipt", "document", "paperwork"]):
        reply = (
            "Create a home records folder with sections for:\n"
            "1. Appliance receipts and warranties.\n"
            "2. Contractor invoices and repair records.\n"
            "3. Insurance and property documents.\n"
            "4. Manuals, model numbers, and service dates.\n\n"
            "Keep sensitive documents in a secure location."
        )
    else:
        reply = (
            "Thank you for contacting HPPUSA AI!\n\n"
            "This is our starter assistant, so its responses are currently "
            "limited to basic home-management guidance. The full AI model "
            "has not been connected yet.\n\n"
            "For the best help, tell me whether you need assistance with "
            "maintenance, repairs, home expenses, or property records."
        )

    return jsonify({"reply": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

