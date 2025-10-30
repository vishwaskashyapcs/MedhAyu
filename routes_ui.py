# routes_ui.py
from flask import Blueprint, render_template_string
from models import CRLog

ui_bp = Blueprint("ui_bp", __name__)

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
setInterval(load, 1500); load();
</script>
</body></html>
"""

@ui_bp.route("/demo/ai/<int:cr_id>")
def demo_ai(cr_id):
    return render_template_string(T, cr_id=cr_id)
