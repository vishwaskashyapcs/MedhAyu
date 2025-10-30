# # routes_chatbot.py
# import os, json, re
# from flask import Blueprint, render_template_string, request, jsonify
# from openai import OpenAI
# from extensions import db
# from models import Department, SOPItem, ChangeRequest
# from flask import Response

# chatbot_bp = Blueprint("chatbot_bp", __name__)
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# SYSTEM_PROMPT = """You are the Pharma Change Control Assistant.
# You help with pharma change requests, SOP mapping, routing logic, and compliance guardrails.

# Rules:
# - Prefer concise, bulleted answers.
# - Use ONLY provided context (departments, SOP catalog, and optional CR).
# - If information is missing, say so and suggest what’s needed.
# - When citing SOPs, reference them by code (e.g., SOP-QC-05).
# - Never invent departments or SOPs not present in the context.
# """

# def _ctx_json(cr_id=None):
#     departments = [d.name for d in db.session.query(Department).all()]
#     sops = [{
#         "code": s.code,
#         "title": s.title,
#         "owner_department": s.owner_department,
#         "snippet": (s.content_snippet or "")[:240],
#     } for s in db.session.query(SOPItem).all()]

#     cr_block = None
#     if cr_id:
#         cr = db.session.get(ChangeRequest, cr_id)
#         if cr:
#             cr_block = {
#                 "id": cr.id,
#                 "title": cr.title,
#                 "department": cr.department,
#                 "risk": cr.risk,
#                 "description": cr.description,
#                 "ai_summary": cr.ai_summary,
#                 "ai_routing": cr.ai_routing,
#             }
#     return {"departments": departments, "sop_catalog": sops, "current_cr": cr_block}

# # ---------- API: /chat/message ----------
# @chatbot_bp.route("/chat/message", methods=["POST"])
# def chat_message():
#     data = request.get_json(silent=True) or {}
#     user_msg = (data.get("message") or "").strip()
#     cr_id = data.get("cr_id")
#     if not user_msg:
#         return jsonify({"reply": "Please type a message."})

#     ctx = _ctx_json(cr_id=cr_id)
#     user_prompt = "CONTEXT:\n" + json.dumps(ctx, ensure_ascii=False) + "\n\nUSER QUESTION:\n" + user_msg

#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_MODEL,
#             temperature=0.2,
#             messages=[{"role": "system", "content": SYSTEM_PROMPT},
#                       {"role": "user", "content": user_prompt}]
#         )
#         text = resp.choices[0].message.content.strip()
#         # Remove Markdown bold/italic symbols like **text**, *text*, or __text__
#         text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)
#     except Exception as e:
#         text = f"Sorry, I couldn’t reach the model: {e}"

#     return jsonify({"reply": text})


# # ---------- UI: /chat ----------
# CHAT_HTML = r"""
# <!doctype html>
# <html lang="en">
# <head>
#   <meta charset="utf-8"/>
#   <title>Chat Assistant</title>
#   <meta name="viewport" content="width=device-width,initial-scale=1"/>
#   <script src="https://cdn.tailwindcss.com"></script>
# </head>
# <body class="bg-gray-100 min-h-screen">
#   <!-- Floating Chat -->
#   <button id="chatFab"
#           class="fixed bottom-6 right-6 rounded-full shadow-xl bg-black text-white w-12 h-12 flex items-center justify-center text-xl"
#           title="Chat">💬</button>

#   <div id="chatWidget"
#        class="hidden fixed bottom-20 right-6 w-[24rem] max-w-[95vw] bg-white rounded-2xl shadow-2xl border overflow-hidden">
#     <div class="px-3 py-2 bg-gray-900 text-white flex items-center justify-between">
#       <div class="font-semibold">Chat Assistant</div>
#       <button id="chatClose" class="text-white/80 hover:text-white">✕</button>
#     </div>

#     <div class="p-3 bg-gray-50">
#       <div class="text-xs text-gray-500 mb-2">
#         Tip: pass a CR id in the URL like <span class="font-mono">/chat?cr_id=12</span> to chat with its context.
#       </div>
#       <div id="chatLog" class="h-56 overflow-y-auto space-y-2 p-2 bg-white rounded border"></div>
#       <div class="mt-2 flex gap-2 items-center">
#         <input id="chatInput" class="flex-1 border rounded p-2 text-sm"
#                placeholder="Ask about routing, SOPs, or this CR…"/>
#         <button id="chatSend" class="bg-black text-white px-3 py-2 rounded text-sm">Send</button>
#       </div>
#       <label class="flex items-center gap-1 text-xs text-gray-600 mt-2">
#         <input id="chatUseCR" type="checkbox" class="accent-black"/>
#         Ask with CR from URL (if provided)
#       </label>
#     </div>
#   </div>

# <script>
#   // Read ?cr_id=... from URL
#   const url = new URL(window.location.href);
#   const crIdFromUrl = url.searchParams.get("cr_id");
#   const chatUseCR = document.getElementById("chatUseCR");
#   if (crIdFromUrl) chatUseCR.checked = true;

#   const chatFab   = document.getElementById("chatFab");
#   const chatWidget= document.getElementById("chatWidget");
#   const chatClose = document.getElementById("chatClose");
#   const chatLog   = document.getElementById("chatLog");
#   const chatInput = document.getElementById("chatInput");
#   const chatSend  = document.getElementById("chatSend");

#   function addChat(role, text) {
#     const bubble = document.createElement("div");
#     const me = role === "user";
#     bubble.className = `max-w-[80%] ${me ? "ml-auto bg-blue-600 text-white" : "mr-auto bg-gray-200 text-gray-900"} px-3 py-2 rounded-xl`;
#     bubble.innerHTML = (text || "").replace(/\\n/g, "<br/>");
#     chatLog.appendChild(bubble);
#     chatLog.scrollTop = chatLog.scrollHeight;
#   }

#   async function sendChat() {
#     const msg = (chatInput.value || "").trim();
#     if (!msg) return;
#     addChat("user", msg);
#     chatInput.value = "";

#     const body = {
#       message: msg,
#       cr_id: (chatUseCR.checked && crIdFromUrl) ? Number(crIdFromUrl) : null
#     };

#     try {
#       const r = await fetch("/chat/message", {
#         method: "POST",
#         headers: {"Content-Type":"application/json"},
#         body: JSON.stringify(body)
#       });
#       const data = await r.json();
#       addChat("assistant", data.reply || "No reply.");
#     } catch (e) {
#       addChat("assistant", "Request failed.");
#     }
#   }

#   chatSend?.addEventListener("click", sendChat);
#   chatInput?.addEventListener("keydown", (e) => {
#     if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
#   });

#   chatFab?.addEventListener("click", () => {
#     chatWidget.classList.toggle("hidden");
#     if (!chatWidget.classList.contains("hidden")) setTimeout(() => chatInput?.focus(), 0);
#   });
#   chatClose?.addEventListener("click", () => chatWidget.classList.add("hidden"));
# </script>
# </body>
# </html>
# """


# EMBED_JS = r"""
# (function(){
#   // Avoid double-inject
#   if (window.__pharmaChatInjected) return;
#   window.__pharmaChatInjected = true;

#   // Create FAB
#   const fab = document.createElement('button');
#   fab.id = 'chatFab';
#   fab.title = 'Chat';
#   fab.textContent = '💬';
#   fab.style.cssText = [
#     'position:fixed','z-index:2147483647','right:24px','bottom:24px',
#     'width:48px','height:48px','border-radius:9999px',
#     'background:#000','color:#fff','font-size:20px','box-shadow:0 8px 24px rgba(0,0,0,.2)',
#     'display:flex','align-items:center','justify-content:center','border:none','cursor:pointer'
#   ].join(';');
#   document.body.appendChild(fab);

#   // Create widget
#   const wrap = document.createElement('div');
#   wrap.id = 'chatWidget';
#   wrap.style.cssText = [
#     'position:fixed','z-index:2147483647','right:24px','bottom:92px',
#     'width:384px','max-width:95vw','background:#fff','border-radius:16px',
#     'box-shadow:0 12px 32px rgba(0,0,0,.2)','border:1px solid #e5e7eb','overflow:hidden',
#     'display:none'
#   ].join(';');

#   wrap.innerHTML = `
#     <div style="background:#111827;color:#fff;padding:8px 12px;display:flex;align-items:center;justify-content:space-between">
#       <div style="font-weight:600">Chat Assistant</div>
#       <button id="chatClose" style="color:#ddd;background:transparent;border:none;font-size:16px;cursor:pointer">✕</button>
#     </div>
#     <div style="padding:12px;background:#f9fafb">
#       <div id="chatLog" style="height:224px;overflow:auto;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:8px"></div>
#       <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
#         <input id="chatInput" placeholder="Ask about routing, SOPs, or this CR…" style="flex:1;border:1px solid #e5e7eb;border-radius:8px;padding:8px;font-size:14px"/>
#         <button id="chatSend" style="background:#000;color:#fff;border:none;border-radius:8px;padding:8px 12px;cursor:pointer">Send</button>
#       </div>
#       <label style="display:flex;align-items:center;gap:6px;color:#6b7280;font-size:12px;margin-top:6px">
#         <input id="chatUseCR" type="checkbox" checked />
#         Ask with current CR (if available)
#       </label>
#     </div>
#   `;
#   document.body.appendChild(wrap);

#   const chatLog   = wrap.querySelector('#chatLog');
#   const chatInput = wrap.querySelector('#chatInput');
#   const chatSend  = wrap.querySelector('#chatSend');
#   const chatClose = wrap.querySelector('#chatClose');
#   const chatUseCR = wrap.querySelector('#chatUseCR');

#   function addChat(role, text){
#     const bubble = document.createElement('div');
#     const me = role === 'user';
#     bubble.style.cssText = [
#       'max-width:80%','padding:8px 12px','border-radius:14px','margin:6px 0',
#       me ? 'margin-left:auto;background:#2563eb;color:#fff' : 'margin-right:auto;background:#e5e7eb;color:#111827'
#     ].join(';');
#     bubble.innerHTML = (text||'').replace(/\n/g,'<br/>');
#     chatLog.appendChild(bubble);
#     chatLog.scrollTop = chatLog.scrollHeight;
#   }

#   async function sendChat(){
#     const msg = (chatInput.value||'').trim();
#     if(!msg) return;
#     addChat('user', msg);
#     chatInput.value = '';

#     // Try to reuse currentCR from page if defined by your UI JS
#     let crId = null;
#     try { if (chatUseCR.checked && typeof window.currentCR !== 'undefined' && window.currentCR) crId = Number(window.currentCR); } catch(e){}

#     try {
#       const r = await fetch('/chat/message', {
#         method:'POST',
#         headers:{'Content-Type':'application/json'},
#         body: JSON.stringify({ message: msg, cr_id: crId })
#       });
#       const data = await r.json();
#       addChat('assistant', data.reply || 'No reply.');
#     } catch(e) {
#       addChat('assistant','Request failed.');
#     }
#   }

#   fab.addEventListener('click', ()=>{
#     wrap.style.display = (wrap.style.display === 'none' || !wrap.style.display) ? 'block' : 'none';
#     if (wrap.style.display === 'block') setTimeout(()=>chatInput.focus(), 0);
#   });
#   chatClose.addEventListener('click', ()=> wrap.style.display = 'none');
#   chatSend.addEventListener('click', sendChat);
#   chatInput.addEventListener('keydown', (e)=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendChat(); }});
# })();
# """

# @chatbot_bp.route("/chat/embed.js", methods=["GET"])
# def chat_embed_js():
#     return Response(EMBED_JS, mimetype="application/javascript")

# # Auto-inject the embed script into HTML responses if CHAT_EMBED=1
# @chatbot_bp.after_app_request
# def inject_chat_widget(response):
#     try:
#         if os.getenv("CHAT_EMBED", "0") != "1":
#             return response
#         ctype = response.headers.get("Content-Type", "")
#         if "text/html" not in ctype.lower():
#             return response
#         body = response.get_data(as_text=True)
#         # Add the embed just before </body>
#         snippet = '<script src="/chat/embed.js"></script></body>'
#         if "</body>" in body:
#             body = body.replace("</body>", snippet)
#             response.set_data(body)
#     except Exception:
#         pass
#     return response

# @chatbot_bp.route("/chat", methods=["GET"])
# def chat_page():
#     return render_template_string(CHAT_HTML)








# routes_chatbot.py
import os, json, re
from flask import Blueprint, render_template_string, request, jsonify, Response
from openai import OpenAI
from extensions import db
from models import Department, SOPItem, ChangeRequest

chatbot_bp = Blueprint("chatbot_bp", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are the Pharma Change Control Assistant.
You help with pharma change requests, SOP mapping, routing logic, and compliance guardrails.

Rules:
- Prefer concise, bulleted answers.
- Use ONLY provided context (departments, SOP catalog, and optional CR).
- If information is missing, say so and suggest what’s needed.
- When citing SOPs, reference them by code (e.g., SOP-QC-05).
- Never invent departments or SOPs not present in the context.
"""

def _ctx_json(cr_id=None):
    departments = [d.name for d in db.session.query(Department).all()]
    sops = [{
        "code": s.code,
        "title": s.title,
        "owner_department": s.owner_department,
        "snippet": (s.content_snippet or "")[:240],
    } for s in db.session.query(SOPItem).all()]

    cr_block = None
    if cr_id:
        cr = db.session.get(ChangeRequest, cr_id)
        if cr:
            cr_block = {
                "id": cr.id,
                "title": cr.title,
                "department": cr.department,
                "risk": cr.risk,
                "description": cr.description,
                "status": cr.status,
                "ai_summary": cr.ai_summary,
                "ai_routing": cr.ai_routing,
            }
    return {"departments": departments, "sop_catalog": sops, "current_cr": cr_block}

# ---- helper: pretty print a CR from DB
def _format_cr_details(cr: ChangeRequest) -> str:
    if not cr:
        return "I couldn’t find that change request."

    lines = []
    lines.append(f"CR #{cr.id}: {cr.title or '—'}")
    lines.append(f"- Status: {cr.status or '—'}")
    lines.append(f"- Department: {cr.department or '—'}")
    lines.append(f"- Risk: {cr.risk or '—'}")
    if cr.description:
        lines.append(f"- Description: {cr.description}")

    # AI summary
    if isinstance(cr.ai_summary, dict):
        prob = cr.ai_summary.get("problem") or []
        just = cr.ai_summary.get("justification") or []
        imp  = cr.ai_summary.get("impact") or []
        if prob or just or imp:
            lines.append("- AI Summary:")
            if prob: lines.append("  • Problem: " + "; ".join([str(x) for x in prob]))
            if just: lines.append("  • Justification: " + "; ".join([str(x) for x in just]))
            if imp:  lines.append("  • Impact: " + "; ".join([str(x) for x in imp]))

    # AI routing
    if isinstance(cr.ai_routing, dict):
        pred = cr.ai_routing.get("predicted_department")
        conf = cr.ai_routing.get("confidence")
        rat  = cr.ai_routing.get("rationale")
        m_sops = cr.ai_routing.get("matched_sops") or []
        if pred or conf is not None or rat or m_sops:
            lines.append("- AI Routing:")
            if pred: lines.append(f"  • Predicted Dept: {pred}")
            if conf is not None: lines.append(f"  • Confidence: {round(float(conf), 2)}")
            if m_sops:
                sop_codes = []
                for s in m_sops:
                    if isinstance(s, str):
                        sop_codes.append(s)
                    elif isinstance(s, dict):
                        sop_codes.append(s.get("code") or "")
                sop_codes = [c for c in sop_codes if c]
                if sop_codes:
                    lines.append("  • Matched SOPs: " + ", ".join(sop_codes))
            if rat:
                lines.append(f"  • Rationale: {rat}")

    return "\n".join(lines)

# ---- parse a CR id from free text like: "#5", "cr 5", "CR#12", "details for 3", etc.
_ID_PATTERNS = re.compile(r'(?:^|\b)(?:#\s*(\d+)|cr\s*#?\s*(\d+)|id\s*#?\s*(\d+))\b', re.I)

def _extract_cr_id(text: str):
    if not text: return None
    m = _ID_PATTERNS.search(text)
    if not m: return None
    for g in m.groups():
        if g and g.isdigit():
            return int(g)
    return None

# ---------- API: /chat/message ----------
@chatbot_bp.route("/chat/message", methods=["POST"])
def chat_message():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    cr_id_from_ui = data.get("cr_id")

    if not user_msg:
        return jsonify({"reply": "Please type a message."})

    # 1) If the user asked for a specific CR (e.g., "details for #5"), return DB details
    asked_id = _extract_cr_id(user_msg)
    target_id = asked_id or (int(cr_id_from_ui) if cr_id_from_ui else None)
    if target_id:
        cr = db.session.get(ChangeRequest, int(target_id))
        if cr:
            return jsonify({"reply": _format_cr_details(cr)})
        else:
            return jsonify({"reply": f"I couldn’t find CR #{target_id}."})

    # 2) Otherwise, ask the model with contextual info (and optional CR from UI)
    ctx = _ctx_json(cr_id=cr_id_from_ui)
    user_prompt = "CONTEXT:\n" + json.dumps(ctx, ensure_ascii=False) + "\n\nUSER QUESTION:\n" + user_msg

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = resp.choices[0].message.content.strip()
        # De-markdown the reply (remove **bold**, *italic*, __underline__)
        text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)
    except Exception as e:
        text = f"Sorry, I couldn’t reach the model: {e}"

    return jsonify({"reply": text})

# ---------- UI (optional: standalone chat page at /chat) ----------
CHAT_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Chat Assistant</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
  <button id="chatFab"
          class="fixed bottom-6 right-6 rounded-full shadow-xl bg-black text-white w-12 h-12 flex items-center justify-center text-xl"
          title="Chat">💬</button>

  <div id="chatWidget"
       class="hidden fixed bottom-20 right-6 w-[24rem] max-w-[95vw] bg-white rounded-2xl shadow-2xl border overflow-hidden">
    <div class="px-3 py-2 bg-gray-900 text-white flex items-center justify-between">
      <div class="font-semibold">Chat Assistant</div>
      <button id="chatClose" class="text-white/80 hover:text-white">✕</button>
    </div>

    <div class="p-3 bg-gray-50">
      <div class="text-xs text-gray-500 mb-2">
        Tip: pass a CR id in the URL like <span class="font-mono">/chat?cr_id=12</span> to chat with its context.
      </div>
      <div id="chatLog" class="h-56 overflow-y-auto space-y-2 p-2 bg-white rounded border"></div>
      <div class="mt-2 flex gap-2 items-center">
        <input id="chatInput" class="flex-1 border rounded p-2 text-sm"
               placeholder="Ask about routing, SOPs, or this CR…"/>
        <button id="chatSend" class="bg-black text-white px-3 py-2 rounded text-sm">Send</button>
      </div>
      <label class="flex items-center gap-1 text-xs text-gray-600 mt-2">
        <input id="chatUseCR" type="checkbox" class="accent-black"/>
        Ask with CR from URL (if provided)
      </label>
    </div>
  </div>

<script>
  const url = new URL(window.location.href);
  const crIdFromUrl = url.searchParams.get("cr_id");
  const chatUseCR = document.getElementById("chatUseCR");
  if (crIdFromUrl) chatUseCR.checked = true;

  const chatFab   = document.getElementById("chatFab");
  const chatWidget= document.getElementById("chatWidget");
  const chatClose = document.getElementById("chatClose");
  const chatLog   = document.getElementById("chatLog");
  const chatInput = document.getElementById("chatInput");
  const chatSend  = document.getElementById("chatSend");

  function addChat(role, text) {
    const bubble = document.createElement("div");
    const me = role === "user";
    bubble.className = `max-w-[80%] ${me ? "ml-auto bg-blue-600 text-white" : "mr-auto bg-gray-200 text-gray-900"} px-3 py-2 rounded-xl`;
    bubble.innerHTML = (text || "").replace(/\\n/g, "<br/>");
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  async function sendChat() {
    const msg = (chatInput.value || "").trim();
    if (!msg) return;
    addChat("user", msg);
    chatInput.value = "";

    const body = {
      message: msg,
      cr_id: (chatUseCR.checked && crIdFromUrl) ? Number(crIdFromUrl) : null
    };

    try {
      const r = await fetch("/chat/message", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(body)
      });
      const data = await r.json();
      addChat("assistant", data.reply || "No reply.");
    } catch (e) {
      addChat("assistant", "Request failed.");
    }
  }

  chatSend?.addEventListener("click", sendChat);
  chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  chatFab?.addEventListener("click", () => {
    chatWidget.classList.toggle("hidden");
    if (!chatWidget.classList.contains("hidden")) setTimeout(() => chatInput?.focus(), 0);
  });
  chatClose?.addEventListener("click", () => chatWidget.classList.add("hidden"));
</script>
</body>
</html>
"""

# ---------- Floating widget embed (auto-injected when CHAT_EMBED=1) ----------
EMBED_JS = r"""
(function(){
  // Avoid double-inject
  if (window.__pharmaChatInjected) return;
  window.__pharmaChatInjected = true;

  // Create FAB
  const fab = document.createElement('button');
  fab.id = 'chatFab';
  fab.title = 'Chat';
  fab.textContent = '💬';
  fab.style.cssText = [
    'position:fixed','z-index:2147483647','right:24px','bottom:24px',
    'width:48px','height:48px','border-radius:9999px',
    'background:#000','color:#fff','font-size:20px','box-shadow:0 8px 24px rgba(0,0,0,.2)',
    'display:flex','align-items:center','justify-content:center','border:none','cursor:pointer'
  ].join(';');
  document.body.appendChild(fab);

  // Create widget
  const wrap = document.createElement('div');
  wrap.id = 'chatWidget';
  wrap.style.cssText = [
    'position:fixed','z-index:2147483647','right:24px','bottom:92px',
    'width:384px','max-width:95vw','background:#fff','border-radius:16px',
    'box-shadow:0 12px 32px rgba(0,0,0,.2)','border:1px solid #e5e7eb','overflow:hidden',
    'display:none'
  ].join(';');

  wrap.innerHTML = `
    <div style="background:#111827;color:#fff;padding:8px 12px;display:flex;align-items:center;justify-content:space-between">
      <div style="font-weight:600">Chat Assistant</div>
      <button id="chatClose" style="color:#ddd;background:transparent;border:none;font-size:16px;cursor:pointer">✕</button>
    </div>
    <div style="padding:12px;background:#f9fafb">
      <div id="chatLog" style="height:224px;overflow:auto;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:8px"></div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
        <input id="chatInput" placeholder="Ask about routing, SOPs, or this CR…" style="flex:1;border:1px solid #e5e7eb;border-radius:8px;padding:8px;font-size:14px"/>
        <button id="chatSend" style="background:#000;color:#fff;border:none;border-radius:8px;padding:8px 12px;cursor:pointer">Send</button>
      </div>
      <label style="display:flex;align-items:center;gap:6px;color:#6b7280;font-size:12px;margin-top:6px">
        <input id="chatUseCR" type="checkbox" checked />
        Ask with current CR (if available)
      </label>
    </div>
  `;
  document.body.appendChild(wrap);

  const chatLog   = wrap.querySelector('#chatLog');
  const chatInput = wrap.querySelector('#chatInput');
  const chatSend  = wrap.querySelector('#chatSend');
  const chatClose = wrap.querySelector('#chatClose');
  const chatUseCR = wrap.querySelector('#chatUseCR');

  function addChat(role, text){
    const bubble = document.createElement('div');
    const me = role === 'user';
    bubble.style.cssText = [
      'max-width:80%','padding:8px 12px','border-radius:14px','margin:6px 0',
      me ? 'margin-left:auto;background:#2563eb;color:#fff' : 'margin-right:auto;background:#e5e7eb;color:#111827'
    ].join(';');
    bubble.innerHTML = (text||'').replace(/\n/g,'<br/>');
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  async function sendChat(){
    const msg = (chatInput.value||'').trim();
    if(!msg) return;
    addChat('user', msg);
    chatInput.value = '';

    // Try to reuse currentCR from the main UI, if present
    let crId = null;
    try { if (chatUseCR.checked && typeof window.currentCR !== 'undefined' && window.currentCR) crId = Number(window.currentCR); } catch(e){}

    try {
      const r = await fetch('/chat/message', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ message: msg, cr_id: crId })
      });
      const data = await r.json();
      addChat('assistant', data.reply || 'No reply.');
    } catch(e) {
      addChat('assistant','Request failed.');
    }
  }

  fab.addEventListener('click', ()=>{
    wrap.style.display = (wrap.style.display === 'none' || !wrap.style.display) ? 'block' : 'none';
    if (wrap.style.display === 'block') setTimeout(()=>chatInput.focus(), 0);
  });
  chatClose.addEventListener('click', ()=> wrap.style.display = 'none');
  chatSend.addEventListener('click', sendChat);
  chatInput.addEventListener('keydown', (e)=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendChat(); }});
})();
"""

@chatbot_bp.route("/chat/embed.js", methods=["GET"])
def chat_embed_js():
    return Response(EMBED_JS, mimetype="application/javascript")

# Auto-inject the embed script into HTML responses if CHAT_EMBED=1
@chatbot_bp.after_app_request
def inject_chat_widget(response):
    try:
        if os.getenv("CHAT_EMBED", "0") != "1":
            return response
        ctype = response.headers.get("Content-Type", "")
        if "text/html" not in ctype.lower():
            return response
        body = response.get_data(as_text=True)
        # Add the embed just before </body>
        snippet = '<script src="/chat/embed.js"></script></body>'
        if "</body>" in body:
            body = body.replace("</body>", snippet)
            response.set_data(body)
    except Exception:
        pass
    return response

@chatbot_bp.route("/chat", methods=["GET"])
def chat_page():
    return render_template_string(CHAT_HTML)

