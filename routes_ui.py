# routes_ui.py
from flask import Blueprint, render_template_string
 
ui_bp = Blueprint("ui_bp", __name__)
 
INDEX = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Intelligent Change Control Assistant</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .fade { animation: fade .4s ease-in-out; }
    @keyframes fade { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  </style>
</head>
<body class="bg-gray-100 min-h-screen p-6">
  <div class="max-w-6xl mx-auto bg-white rounded-2xl shadow-xl p-6 fade">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">🧠 Intelligent Change Control Assistant</h1>
      <div class="flex items-center gap-2">
        <label class="text-sm text-gray-600">Role:</label>
        <select id="roleSelect" class="border px-3 py-2 rounded text-sm bg-gray-50">
          <option value="user">User</option>
          <option value="dept_head">Department Admin</option>
          <option value="qa">Super Admin (QA)</option>
        </select>
        <select id="actorSelect" class="border px-3 py-2 rounded text-sm bg-gray-50">
          <!-- populated from /_debug/dept_heads for convenience -->
        </select>
      </div>
    </div>
 
    <!-- USER -->
    <section id="userSection" class="mt-6 space-y-3">
      <h2 class="text-xl font-semibold mb-2">Raise Change Request</h2>
      <input id="crTitle" class="w-full border rounded p-2" placeholder="Title (optional)"/>
      <textarea id="crDesc" class="w-full p-3 border rounded-lg mb-1" rows="5" placeholder="Describe your change request..."></textarea>
      <div class="flex items-center gap-2 flex-wrap">
        <input id="declaredDept" class="border rounded p-2 w-72" placeholder="Declared department (optional)" />
        <button id="btnMicServer" class="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700">☁️ Dictate (server)</button>
        <span id="micStatus" class="text-sm text-gray-500"></span>
        <button id="btnSubmit" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">📤 Submit</button>
        <button id="btnRunAI" class="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700" disabled>🚀 Run AI</button>
        <a id="linkLogs" class="text-sm text-blue-600 underline hidden" target="_blank">live logs</a>
      </div>
 
      <div id="aiProgress" class="mt-2 hidden">
        <div class="text-sm text-gray-500">Processing…</div>
        <ul id="aiSteps" class="mt-1 space-y-1 text-gray-700 mono"></ul>
      </div>
 
      <div id="aiResult" class="hidden mt-3 bg-green-50 p-4 rounded-lg border border-green-200">
        <h3 class="font-semibold text-green-700 mb-2">AI Result</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p class="text-sm text-gray-600 mb-1">Summary</p>
            <!-- CHANGED: pre → div so we can inject rich HTML -->
            <div id="summary" class="text-sm bg-white border rounded p-2"></div>
          </div>
          <div class="mt-3">
            <button id="btnSpeak" class="bg-teal-600 text-white px-3 py-1 rounded hover:bg-teal-700">🔊 Speak Result</button>
          </div>
 
          <div>
            <p class="text-sm text-gray-600 mb-1">Routing</p>
            <div class="text-sm">
              <div><b>Predicted Dept:</b> <span id="predDept"></span></div>
              <div><b>Owner:</b> <span id="owner"></span></div>
              <div id="confidenceRow"><b>Confidence:</b> <span id="confidence"></span></div>
              <div><b>Matched SOPs:</b> <span id="sops"></span></div>
              <div><b>Rationale:</b> <span id="rationale"></span></div>
            </div>
          </div>
        </div>
      </div>
    </section>
 
    <!-- DEPT ADMIN -->
    <section id="adminSection" class="mt-8 hidden">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold">Department Inbox</h2>
        <button id="btnRefreshInbox" class="text-sm bg-gray-800 text-white px-3 py-1 rounded">Refresh</button>
      </div>
      <div id="adminList" class="mt-3 space-y-3"></div>
    </section>
 
    <!-- QA -->
    <section id="superSection" class="mt-8 hidden">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold">QA Board</h2>
        <button id="btnRefreshQA" class="text-sm bg-gray-800 text-white px-3 py-1 rounded">Refresh</button>
      </div>
      <div id="superList" class="mt-3 space-y-3"></div>
    </section>
  </div>
 
 
 <style>
  
  #confidenceRow { display: none; }
</style>

<script>
const roleSelect   = document.getElementById("roleSelect");
const actorSelect  = document.getElementById("actorSelect");
const userSection  = document.getElementById("userSection");
const adminSection = document.getElementById("adminSection");
const superSection = document.getElementById("superSection");
 
const btnMicServer = document.getElementById("btnMicServer");
const micStatus    = document.getElementById("micStatus");
const btnSpeak     = document.getElementById("btnSpeak");
 
const crTitle = document.getElementById("crTitle");
const crDesc  = document.getElementById("crDesc");
const decDept = document.getElementById("declaredDept");
const btnSubmit = document.getElementById("btnSubmit");
const btnRunAI  = document.getElementById("btnRunAI");
const linkLogs  = document.getElementById("linkLogs");
 
const aiProgress = document.getElementById("aiProgress");
const aiSteps    = document.getElementById("aiSteps");
const aiResult   = document.getElementById("aiResult");
const summary    = document.getElementById("summary");
const predDept   = document.getElementById("predDept");
const owner      = document.getElementById("owner");
const confidence = document.getElementById("confidence");
const rationale  = document.getElementById("rationale");
const sops       = document.getElementById("sops");
 
const adminList  = document.getElementById("adminList");
const superList  = document.getElementById("superList");
const btnRefreshInbox = document.getElementById("btnRefreshInbox");
const btnRefreshQA    = document.getElementById("btnRefreshQA");
 
let currentCR = null;
let logTimer = null;
 
// --------- NEW: nice render helpers ----------
let lastSummary = null;
 
function renderBullets(items) {
  const arr = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!arr.length) return '<div class="text-sm text-gray-500">—</div>';
  return `<ul class="list-disc ml-5 space-y-1 text-sm">
    ${arr.map(x => `<li>${x}</li>`).join("")}
  </ul>`;
}
 
function renderSummary(sum) {
  lastSummary = sum || {};
  return `
    <div class="space-y-4">
      <div>
        <div class="font-semibold text-gray-800">Problem</div>
        ${renderBullets(sum?.problem)}
      </div>
      <div>
        <div class="font-semibold text-gray-800">Justification</div>
        ${renderBullets(sum?.justification)}
      </div>
      <div>
        <div class="font-semibold text-gray-800">Impact</div>
        ${renderBullets(sum?.impact)}
      </div>
    </div>`;
}
 
function renderSopChips(sopsArr) {
  if (!Array.isArray(sopsArr) || !sopsArr.length) return "—";
  return sopsArr.map(s => {
    const code = typeof s === "string" ? s : (s.code || "");
    return `<span class="inline-block px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 text-xs mr-1 mb-1">${code}</span>`;
  }).join("");
}
// ---------------------------------------------
 
function setRoleUI() {
  userSection.classList.add("hidden");
  adminSection.classList.add("hidden");
  superSection.classList.add("hidden");
 
  const r = roleSelect.value;
  if (r === "user") userSection.classList.remove("hidden");
  if (r === "dept_head") adminSection.classList.remove("hidden");
  if (r === "qa") superSection.classList.remove("hidden");
}
 
// ---- Server-side STT using MediaRecorder → /voice/stt ----
let mediaRecorder = null;
let chunks = [];
let recording = false;
 
btnMicServer.addEventListener("click", async () => {
  if (!recording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      chunks = [];
      mediaRecorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
      mediaRecorder.onstop = async () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob, "audio.webm");
        micStatus.textContent = "Uploading audio…";
        const resp = await fetch("/voice/stt", { method:"POST", body: form });
        if (!resp.ok) {
          micStatus.textContent = "Server STT failed.";
          return;
        }
        const data = await resp.json();
        const t = (data.text || "").trim();
        if (t) {
          const low = t.toLowerCase();
          if (low.startsWith("title ")) {
            crTitle.value = t.replace(/^title\s+/i, "");
            micStatus.textContent = "Title set (server STT).";
          } else if (low.startsWith("department ") || low.startsWith("declared department ")) {
            decDept.value = t.replace(/^(declared\s+)?department\s+/i, "");
            micStatus.textContent = "Declared department set (server STT).";
          } else {
            const sep = crDesc.value && !crDesc.value.endsWith("\n") ? "\n" : "";
            crDesc.value = (crDesc.value || "") + sep + t;
            micStatus.textContent = "Description updated (server STT).";
          }
        } else {
          micStatus.textContent = "No speech recognized.";
        }
      };
      mediaRecorder.start();
      recording = true;
      btnMicServer.textContent = "☁️ Stop";
      micStatus.textContent = "Recording (server)…";
    } catch (e) {
      micStatus.textContent = "Mic error: " + e.message;
    }
  } else {
    recording = false;
    btnMicServer.textContent = "☁️ Dictate (server)";
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    micStatus.textContent = "Processing…";
  }
});
 
// ---- Speak AI Result (TTS) ----
btnSpeak?.addEventListener("click", () => {
  const synth = window.speechSynthesis;
  if (!synth) return alert("SpeechSynthesis not supported.");
  const parts = [];
  if (predDept.textContent) parts.push(`Predicted department: ${predDept.textContent}.`);
  if (owner.textContent && owner.textContent !== "—") parts.push(`Owner: ${owner.textContent}.`);
  if (confidence.textContent) parts.push(`Confidence: ${confidence.textContent}.`);
  const probs = Array.isArray(lastSummary?.problem) ? lastSummary.problem.slice(0,2).join("; ") : "";
  if (probs) parts.push(`Key problems: ${probs}.`);
  const text = parts.join(" ") || "No AI result to speak yet.";
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 1.0;
  synth.cancel();
  synth.speak(utter);
});
 
roleSelect.addEventListener("change", setRoleUI);
 
async function loadHeads() {
  const r = await fetch("/_debug/dept_heads");
  const heads = await r.json();
  actorSelect.innerHTML = "";
  for (const [dept, info] of Object.entries(heads)) {
    const opt = document.createElement("option");
    opt.value = info.user_id;
    opt.textContent = `${dept} — ${info.name} (#${info.user_id})`;
    actorSelect.appendChild(opt);
  }
}
loadHeads().then(setRoleUI);
 
// Submit CR
btnSubmit.addEventListener("click", async () => {
  const body = {
    title: crTitle.value || "",
    description: crDesc.value || "",
    declared_department: decDept.value || null
  };
  if (!body.description.trim()) { alert("Please add a description."); return; }
 
  const r = await fetch("/cr/submit", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
  const data = await r.json();
  currentCR = data.cr_id;
  btnRunAI.disabled = false;
  linkLogs.classList.remove("hidden");
  linkLogs.href = `/demo/ai/${currentCR}`;
  aiResult.classList.add("hidden");
  aiSteps.innerHTML = "";
  aiProgress.classList.add("hidden");
  alert(`CR #${currentCR} created (status: ${data.status}). Click "Run AI".`);
});
 
// Run AI
btnRunAI.addEventListener("click", async () => {
  if (!currentCR) { alert("Submit a CR first."); return; }
  aiProgress.classList.remove("hidden");
  aiSteps.innerHTML = `<li class="mono">… calling AI</li>`;
  aiResult.classList.add("hidden");
 
  // start polling logs
  if (logTimer) clearInterval(logTimer);
  logTimer = setInterval(async () => {
    const r = await fetch(`/cr/${currentCR}/logs`);
    if (!r.ok) return;
    const logs = await r.json();
    aiSteps.innerHTML = logs.map(l => `<li class="mono">[${l.ts}] <b>${l.stage}</b> — ${l.message}</li>`).join("");
  }, 1200);
 
  const r = await fetch(`/cr/${currentCR}/run_ai`, { method:"POST" });
  const data = await r.json();
 
  if (logTimer) { clearInterval(logTimer); logTimer = null; }
 
  aiProgress.classList.add("hidden");
  aiResult.classList.remove("hidden");
 
  // CHANGED: render a human-friendly summary & SOP chips
  summary.innerHTML = renderSummary(data.summary);
  predDept.textContent = data.predicted_department || "—";
  owner.textContent = data.owner_name ? `${data.owner_name} (id ${data.owner_user_id})` : "—";
  confidence.textContent = data.confidence?.toFixed ? data.confidence.toFixed(2) : String(data.confidence ?? "—");
  rationale.textContent = data.rationale || "—";
  sops.innerHTML = renderSopChips(data.matched_sops);
});
 
// Admin inbox (dept_head)
btnRefreshInbox.addEventListener("click", loadInbox);
async function loadInbox() {
  const uid = actorSelect.value || 2; // default to Manufacturing head
  const r = await fetch(`/inbox/dept_head/${uid}`);
  const data = await r.json();
  adminList.innerHTML = "";
  if (!Array.isArray(data)) {
    adminList.innerHTML = `<div class="text-sm text-red-600">Error: ${data.error || 'unknown'}</div>`;
    return;
  }
  data.forEach(cr => {
    const div = document.createElement("div");
    div.className = "border p-3 rounded bg-gray-50";
    div.innerHTML = `
      <div class="flex items-center justify-between">
        <div>
          <div class="font-semibold">#${cr.id}: ${cr.title}</div>
          <div class="text-sm text-gray-600">Status: <span class="text-blue-700">${cr.status}</span></div>
        </div>
        <div class="flex gap-2">
          <button class="approve bg-green-600 text-white px-3 py-1 rounded" data-id="${cr.id}">Approve</button>
          <button class="reroute bg-yellow-600 text-white px-3 py-1 rounded" data-id="${cr.id}">Reroute…</button>
        </div>
      </div>
    `;
    adminList.appendChild(div);
  });
 
  adminList.querySelectorAll(".approve").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      const r = await fetch(`/cr/${id}/approve`, { method:"POST" });
      if (r.ok) { loadInbox(); } else { alert("approve failed"); }
    });
  });
 
  adminList.querySelectorAll(".reroute").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      const to = prompt("Reroute to department (exact name):", "Engineering");
      if (!to) return;
      const r = await fetch(`/cr/${id}/reroute`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ to_department: to })
      });
      if (r.ok) { loadInbox(); } else { alert("reroute failed"); }
    });
  });
}
 
// QA board
btnRefreshQA.addEventListener("click", loadQA);
async function loadQA() {
  const r = await fetch(`/board/qa`);
  const data = await r.json();
  superList.innerHTML = "";
  (data || []).forEach(cr => {
    const div = document.createElement("div");
    const ai = cr.ai || {};
    div.className = "border p-3 rounded bg-gray-50";
    div.innerHTML = `
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <div class="font-semibold">#${cr.id}: ${cr.title}</div>
          <div class="text-sm">Dept: <b>${cr.dept || '—'}</b> · Status: <b>${cr.status}</b></div>
          <div class="text-xs mt-1 text-gray-600 mono overflow-auto">${JSON.stringify(ai, null, 2)}</div>
        </div>
        <div class="flex items-start gap-2">
          <input class="dept border rounded p-1" placeholder="Override dept (exact)" value="${cr.dept || ''}"/>
          <select class="status border rounded p-1">
            ${["NEW","IN_REVIEW","QA_REVIEW","IMPLEMENTED","CLOSED"].map(s => `<option ${s===cr.status?'selected':''}>${s}</option>`).join("")}
          </select>
          <button class="apply bg-indigo-600 text-white px-3 py-1 rounded" data-id="${cr.id}">Apply</button>
        </div>
      </div>
    `;
    superList.appendChild(div);
  });
 
  superList.querySelectorAll(".apply").forEach(btn => {
    btn.addEventListener("click", async () => {
      const row = btn.closest("div.border");
      const dept = row.querySelector(".dept").value;
      const status = row.querySelector(".status").value;
      const id = btn.getAttribute("data-id");
      const r = await fetch(`/cr/${id}/override`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ department: dept, status })
      });
      if (!r.ok) alert("override failed");
      else loadQA();
    });
  });
}
 
// initial
setRoleUI();
</script>
</body>
</html>
"""
 
@ui_bp.route("/")
def index():
    return render_template_string(INDEX)
 
 
# (you already had this — keep it for live stage view)
T = """
<!doctype html><html><body style="font-family:sans-serif">
<h2>CR {{cr_id}} — AI Stages</h2>
<div id="logs"></div>
<script>
async function load() {
  const r = await fetch('/cr/{{cr_id}}/logs');
  const data = await r.json();
  document.getElementById('logs').innerHTML =
    data.map(x => `<div>[${x.ts}] <b>${x.stage}</b>: ${x.message}</div>`).join('');
}
setInterval(load, 1200); load();
</script>
</body></html>
"""
@ui_bp.route("/demo/ai/<int:cr_id>")
def demo_ai(cr_id):
    return render_template_string(T, cr_id=cr_id)
 