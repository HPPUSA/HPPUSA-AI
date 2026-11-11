
import ipaddress
import os
import time
from collections import OrderedDict, deque
from threading import Lock
from uuid import uuid4

from flask import Flask, request, jsonify, render_template_string
from groq import Groq

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

# Lightweight process-local protection suitable for the initial Free-tier test.
# The client address is taken from the WSGI request, not an untrusted header.
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_TRACKED_CLIENTS = 5000
_request_history = OrderedDict()
_request_history_lock = Lock()


def _normalize_rate_limit_client_key(client_key):
    """Return one canonical IP address, or None for an untrusted identity."""
    if not isinstance(client_key, str):
        return None
    try:
        return ipaddress.ip_address(client_key.strip()).compressed
    except ValueError:
        return None


def _get_rate_limit_client_key():
    # Render documents Cloudflare as the ingress for public web-service traffic.
    # Its Cloudflare integration supplies CF-Connecting-IP to the origin.
    # Do not use X-Forwarded-For: caller-provided values can be retained in its chain.
    # A local Flask test client can set CF-Connecting-IP itself; that does not
    # model or validate the Cloudflare edge trust boundary.
    return _normalize_rate_limit_client_key(
        request.headers.get("CF-Connecting-IP")
    )


_CLIENT_KEY_UNSET = object()


def _chat_rate_limit_exceeded(client_key=_CLIENT_KEY_UNSET):
    if client_key is _CLIENT_KEY_UNSET:
        client_key = _get_rate_limit_client_key()
    # Validate even explicitly supplied keys: callers cannot bypass the
    # identity boundary by passing an arbitrary string or non-string value.
    client_key = _normalize_rate_limit_client_key(client_key)
    if client_key is None:
        return True

    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    with _request_history_lock:
        history = _request_history.get(client_key)
        if history is None:
            if len(_request_history) >= MAX_TRACKED_CLIENTS:
                # Reclaim only expired records. Never evict an active client's
                # history and silently grant that identity a fresh request bucket.
                expired_keys = []
                for tracked_key, tracked_history in _request_history.items():
                    while tracked_history and tracked_history[0] <= cutoff:
                        tracked_history.popleft()
                    if not tracked_history:
                        expired_keys.append(tracked_key)
                for expired_key in expired_keys:
                    del _request_history[expired_key]

                # Preserve existing protections when capacity is still full.
                # New identities are temporarily blocked until a slot expires.
                if len(_request_history) >= MAX_TRACKED_CLIENTS:
                    return True

            history = deque()
            _request_history[client_key] = history
        else:
            _request_history.move_to_end(client_key)
            while history and history[0] <= cutoff:
                history.popleft()

        if len(history) >= RATE_LIMIT_REQUESTS:
            return True

        history.append(now)
        return False


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Your request is too large. Please shorten it and try again."}), 413

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
<script src="https://cdn.jsdelivr.net/npm/marked@18.1.3/lib/marked.umd.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.4.17/dist/purify.min.js"></script>
<script>
marked.setOptions({
  gfm: true,
  breaks: true
});

function formatReply(text) {
  const cleaned = String(text)
    .replace(/\\\\(?=\\s*\\n)/g, '')
    .replace(/&amp;#x20;|&#x20;|&#32;/gi, ' ')
    .replace(/&amp;#91;|&#91;/gi, '[')
    .replace(/&amp;#93;|&#93;/gi, ']');

  const html = marked.parse(cleaned);
  const safeHtml = DOMPurify.sanitize(html);

  const container = document.createElement('div');
  container.innerHTML = safeHtml;

  container.querySelectorAll('*').forEach((element) => {
    element.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        node.textContent = node.textContent
          .replace(/&#x20;|&#32;/gi, ' ')
          .replace(/&#91;/gi, '[')
          .replace(/&#93;/gi, ']');
      }
    });
  });

  return DOMPurify.sanitize(container.innerHTML);
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
    client_key = _get_rate_limit_client_key()
    if client_key is None:
        response = jsonify({
            "error": "HPPUSA AI cannot verify the request source right now. Please try again shortly."
        })
        response.status_code = 503
        response.headers["Retry-After"] = str(RATE_LIMIT_WINDOW_SECONDS)
        return response

    if _chat_rate_limit_exceeded(client_key):
        response = jsonify({"error": "Too many requests. Please wait a moment before trying again."})
        response.status_code = 429
        response.headers["Retry-After"] = str(RATE_LIMIT_WINDOW_SECONDS)
        return response

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Please send your question as a JSON object."}), 400

    raw_message = data.get("message")
    if not isinstance(raw_message, str):
        return jsonify({"error": "Please enter a question."}), 400

    message = raw_message.strip()
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
        # Keep provider waits below Gunicorn's default 30-second worker timeout.
        # Disable SDK retries so one request has a predictable upper bound.
        client = Groq(api_key=api_key, timeout=25.0, max_retries=0)

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

                        
                        "For home repairs, prioritize safety over completing the repair. "
                        "For plumbing leaks, advise the homeowner to shut off the "
                        "appropriate water supply only if the shutoff is safely accessible "
                        "without entering a hazardous area or approaching water near "
                        "electrical hazards. Never instruct the homeowner to approach or "
                        "operate a shutoff, breaker, or electrical panel in an affected "
                        "hazardous area. Do not recommend tightening, loosening, "
                        "disassembling, or attempting to repair a leaking plumbing "
                        "connection as a troubleshooting step or as a suggested repair "
                        "for the homeowner to perform. Never recommend turning the water "
                        "back on to test a connection that is leaking or may still be "
                        "leaking. Do not suggest repeated tightening or repeated testing. "
                        "Do not recommend placing towels, rags, pans, buckets, containers, "
                        "or other objects to catch, absorb, contain, block, or redirect "
                        "leaking water when electrical hazards may be present. Keep people "
                        "and pets away from water near outlets, wiring, or electrical "
                        "equipment; move to a dry, safe location and do not touch wet "
                        "equipment or enter standing water that may be electrically "
                        "energized. If there are sparks, smoke, fire, crackling, or "
                        "suspected electric shock, advise moving to safety and calling "
                        "emergency services. Otherwise, recommend a qualified electrician "
                        "for the electrical hazard and a qualified plumber for the leak. "
                        "A qualified plumber should determine and perform the appropriate "
                        "repair based on the fitting's type and condition; do not prescribe "
                        "a specific repair without professional assessment. Recommend a "
                        "qualified plumber if the leak continues, the source is unclear, "
                        "a fitting appears damaged or corroded, or the homeowner is unsure "
                        "how to proceed. Do not advise restoring power until a qualified "
                        "professional confirms it is safe. Encourage documenting the issue "
                        "from a safe distance without taking risks. Do not repeat "
                        "prohibited actions in steps, checklists, summaries, or next steps. "
                        "For electrical work, gas, structural problems, major plumbing, "
                        "or other potentially dangerous tasks, explain the risks and "
                        "recommend a qualified professional when appropriate. "
                        "For HVAC troubleshooting, start with simple, safe checks such "
                        "as thermostat settings, a visibly dirty filter, and unobstructed "
                        "vents. Do not instruct homeowners to reset a tripped breaker "
                        "repeatedly, open electrical panels or equipment compartments, "
                        "touch refrigerant lines, or handle refrigerant. If a breaker "
                        "trips, leave it off and contact a qualified HVAC technician or "
                        "electrician. Only suggest clearing loose debris around an "
                        "outdoor unit when it can be done safely without touching the "
                        "equipment. Refer persistent cooling problems to a qualified "
                        "HVAC technician. "

                       "WATER NEAR ELECTRICITY — STRICT SAFETY OVERRIDE: If water "
                        "is near an outlet, wiring, electrical equipment, or a potentially "
                        "energized area, tell the homeowner to keep people and pets away "
                        "and move to a dry, safe location. Never instruct or suggest that "
                        "the homeowner approach, inspect, or operate a breaker or electrical "
                        "panel, approach or operate a water shutoff in the affected area, "
                        "or touch wet equipment. Never suggest using or placing buckets, "
                        "towels, mops, cardboard, boards, barriers, tools, or other objects "
                        "to absorb, contain, block, redirect, or clean up water in or near "
                        "the affected area. Do not include any of these prohibited actions "
                        "in steps, checklists, summaries, or next steps. If there are sparks, "
                        "smoke, fire, crackling, or suspected electric shock, tell the "
                        "homeowner to move away to safety and call emergency services. "
                        "Otherwise, advise contacting a qualified electrician for the "
                        "electrical hazard and a qualified plumber for the leak. Do not "
                        "advise restoring power until a qualified professional confirms "
                        "it is safe. Prioritize safety over cost and ask one question at "
                        "a time. "
                        "Do not claim to be a licensed contractor or other licensed "
                        "professional. Be respectful, patient, and encouraging. Help "
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
        request_id = uuid4().hex[:12]
        # Do not log prompts, credentials, provider payloads, or raw exception text.
        app.logger.error(
            "Groq request failed (request_id=%s, error_type=%s)",
            request_id,
            type(error).__name__,
        )
        return jsonify({
            "error": "HPPUSA AI could not complete the request right now. Please try again.",
            "request_id": request_id,
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


