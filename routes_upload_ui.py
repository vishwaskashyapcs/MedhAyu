# routes_upload_ui.py
from flask import Blueprint, render_template_string

upload_ui_bp = Blueprint("upload_ui_bp", __name__)

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Upload CR Document</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}</style>
</head>
<body class="bg-gray-100 min-h-screen p-6">
  <div class="max-w-2xl mx-auto bg-white rounded-2xl shadow-xl p-6">
    <h1 class="text-2xl font-bold mb-1">📄 Upload Change Request</h1>
    <p class="text-sm text-gray-600 mb-4">
      Please use the <a href="/upload/template" class="text-blue-600 underline">fixed format template</a> (TXT).
    </p>

    <form id="frm" class="space-y-3">
      <input type="file" id="file" name="file" accept=".txt,.docx,.pdf"
             class="block w-full border rounded p-2" />
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" id="auto" class="accent-black" checked />
        Run AI right after creating the CR
      </label>
      <button id="btnUp" type="button"
              class="bg-black text-white px-4 py-2 rounded">Upload & Create</button>
    </form>

    <div id="out" class="mt-5 hidden">
      <h2 class="text-lg font-semibold">Result</h2>
      <div id="err" class="hidden text-red-600 text-sm"></div>

      <div id="ok" class="hidden space-y-2">
        <div class="text-sm">Created CR <b id="crid"></b> — status: <b id="crst"></b></div>
        <div class="text-sm">
          <div><b>Parsed Title:</b> <span id="pt"></span></div>
          <div><b>Parsed Dept:</b> <span id="pd"></span></div>
          <div><b>Parsed Risk:</b> <span id="pr"></span></div>
          <div><b>Description:</b></div>
          <pre id="px" class="mono whitespace-pre-wrap bg-gray-50 border rounded p-2"></pre>
        </div>

        <div id="aiBlock" class="hidden">
          <h3 class="font-semibold mt-2">AI Result</h3>
          <div class="text-sm">
            <div><b>Predicted Dept:</b> <span id="apd"></span></div>
            <div><b>Owner:</b> <span id="aown"></span></div>
            <div><b>Confidence:</b> <span id="acf"></span></div>
            <div><b>Matched SOPs:</b> <span id="ams"></span></div>
            <div><b>Rationale:</b> <span id="art"></span></div>
          </div>
        </div>

        <div class="mt-3 flex gap-2">
          <a id="lnkLogs" class="text-blue-600 underline" target="_blank">Live logs</a>
          <a id="lnkRun" class="text-blue-600 underline" target="_blank">Run AI (if not run)</a>
          <a href="/" class="text-gray-700 underline">Back to main UI</a>
        </div>
      </div>
    </div>
  </div>

<script>
const file = document.getElementById("file");
const auto = document.getElementById("auto");
const btnUp= document.getElementById("btnUp");
const out  = document.getElementById("out");
const err  = document.getElementById("err");
const ok   = document.getElementById("ok");

const crid = document.getElementById("crid");
const crst = document.getElementById("crst");
const pt   = document.getElementById("pt");
const pd   = document.getElementById("pd");
const pr   = document.getElementById("pr");
const px   = document.getElementById("px");

const aiBlock = document.getElementById("aiBlock");
const apd = document.getElementById("apd");
const aown= document.getElementById("aown");
const acf = document.getElementById("acf");
const ams = document.getElementById("ams");
const art = document.getElementById("art");

const lnkLogs = document.getElementById("lnkLogs");
const lnkRun  = document.getElementById("lnkRun");

btnUp.addEventListener("click", async () => {
  err.classList.add("hidden");
  ok.classList.add("hidden");
  out.classList.remove("hidden");

  const f = file.files[0];
  if (!f) { err.textContent = "Please choose a file."; err.classList.remove("hidden"); return; }

  const form = new FormData();
  form.append("file", f);
  if (auto.checked) form.append("auto_run_ai", "1");

  const r = await fetch("/upload/parse", { method:"POST", body: form });
  const data = await r.json();

  if (!r.ok || data.error) {
    err.textContent = data.error || "Upload failed.";
    err.classList.remove("hidden");
    return;
  }

  // Show parsed + created CR
  crid.textContent = data.cr_id;
  crst.textContent = data.status;
  pt.textContent   = data.parsed.title || "—";
  pd.textContent   = data.parsed.department || "—";
  pr.textContent   = data.parsed.risk || "—";
  px.textContent   = data.parsed.description || "—";

  lnkLogs.href = data.links.logs;
  lnkRun.href  = data.links.run_ai;

  // Optional AI payload
  if (data.ai && !data.ai.error) {
    aiBlock.classList.remove("hidden");
    apd.textContent = data.ai.predicted_department || "—";
    aown.textContent= data.ai.owner_name ? `${data.ai.owner_name} (id ${data.ai.owner_user_id})` : "—";
    acf.textContent = (typeof data.ai.confidence === "number") ? data.ai.confidence.toFixed(2) : "—";
    // matched_sops can be strings or {code:...}
    const arr = Array.isArray(data.ai.matched_sops) ? data.ai.matched_sops : [];
    const codes = arr.map(s => typeof s === "string" ? s : (s.code || "")).filter(Boolean);
    ams.textContent = codes.length ? codes.join(", ") : "—";
    art.textContent = data.ai.rationale || "—";
  } else {
    aiBlock.classList.add("hidden");
  }

  ok.classList.remove("hidden");
});
</script>
</body>
</html>
"""

@upload_ui_bp.route("/uploader", methods=["GET"])
def uploader_page():
    return render_template_string(PAGE)
