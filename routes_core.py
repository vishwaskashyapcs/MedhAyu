# from flask import Blueprint, jsonify
# from ai_llm import run_ai_for_cr

# ai_bp = Blueprint("ai_bp", __name__)

# @ai_bp.route("/ai/run/<int:cr_id>", methods=["POST"])
# def ai_run(cr_id):
#     data, err = run_ai_for_cr(cr_id)
#     if err:
#         return jsonify({"error": err}), 404
#     return jsonify(data), 200

from flask import Blueprint, request, jsonify
from extensions import db
from models import ChangeRequest, User, Department, CRLog
from utils import log_stage
from utils_sla import compute_sla_for, set_status

core_bp = Blueprint("core_bp", __name__)

# ---- Auth stub (no passwords; for demo only)
@core_bp.route("/login", methods=["POST"])
def login():
    """
    Accepts: {"email":"...", "as_role":"user|dept_head|qa"}
    Demo only: it sets a fake session role in memory (return it to client)
    """
    data = request.get_json(silent=True) or {}
    return jsonify({"token":"demo", "role": data.get("as_role","user"), "email": data.get("email")})

# ---- Submit or paste a CR (normal user)
@core_bp.route("/cr/submit", methods=["POST"])
def submit_cr():
    """
    { "title": "...", "description": "...", "declared_department": "Manufacturing" }
    """
    data = request.get_json(silent=True) or {}
    cr = ChangeRequest(
        title=data.get("title",""),
        description=data.get("description",""),
        department=data.get("declared_department") or None,
        status="NEW"
    )
    db.session.add(cr)
    db.session.commit()
    log_stage(cr.id, "submit", f"CR submitted; declared_dept={cr.department or '—'}")
    return jsonify({"cr_id": cr.id, "status": cr.status})

# ---- Trigger AI for a CR (normal user clicks 'Run AI')
@core_bp.route("/cr/<int:cr_id>/run_ai", methods=["POST"])
def run_ai(cr_id):
    from ai_llm import run_ai_for_cr
    data, err = run_ai_for_cr(cr_id)
    if err:
        return jsonify({"error": err}), 404
    return jsonify(data)

# ---- Get logs (to show AI stages progress)
@core_bp.route("/cr/<int:cr_id>/logs", methods=["GET"])
def cr_logs(cr_id):
    logs = CRLog.query.filter_by(cr_id=cr_id).order_by(CRLog.ts.asc()).all()
    return jsonify([
        {"stage": l.stage, "message": l.message, "level": l.level, "ts": l.ts.isoformat()}
        for l in logs
    ])

# ---- Dept Head Inbox (approvals assigned to their department)
@core_bp.route("/inbox/dept_head/<int:user_id>", methods=["GET"])
def inbox_dept_head(user_id):
    u = db.session.get(User, user_id)
    if not u or u.role != "dept_head":
        return jsonify({"error":"not a dept_head"}), 403
    d = db.session.get(Department, u.department_id)
    crs = ChangeRequest.query.filter_by(department=d.name).filter(ChangeRequest.status.in_(["IN_REVIEW","NEW"])).all()
    return jsonify([{"id": c.id, "title": c.title, "status": c.status} for c in crs])

# ---- Dept Head actions: approve or re-route
@core_bp.route("/cr/<int:cr_id>/approve", methods=["POST"])
def approve_cr(cr_id):
    c = db.session.get(ChangeRequest, cr_id)
    if not c: return jsonify({"error":"CR not found"}), 404
    set_status(c, "QA_REVIEW", note="Dept head approved")
    db.session.commit()
    log_stage(c.id, "approve", "Dept head approved; moved to QA_REVIEW")
    return jsonify({"ok": True, "status": c.status})

@core_bp.route("/cr/<int:cr_id>/reroute", methods=["POST"])
def reroute_cr(cr_id):
    body = request.get_json(silent=True) or {}
    target_dept = body.get("to_department")
    c = db.session.get(ChangeRequest, cr_id)
    if not c: return jsonify({"error":"CR not found"}), 404
    c.department = target_dept
    set_status(c, "IN_REVIEW", note=f"Rerouted to {target_dept}")
    db.session.commit()
    log_stage(c.id, "reroute", f"Dept head rerouted: {old or '—'} → {target_dept}")
    return jsonify({"ok": True, "status": c.status, "department": c.department})

# ---- QA Board (super admin)
@core_bp.route("/board/qa", methods=["GET"])
def qa_board():
    crs = ChangeRequest.query.order_by(ChangeRequest.id.asc()).all()
    out = []
    for c in crs:
        out.append({
            "id": c.id, "title": c.title, "dept": c.department,
            "status": c.status, "ai": c.ai_routing
        })
    return jsonify(out)

# ---- QA override (manual changes)
@core_bp.route("/cr/<int:cr_id>/override", methods=["POST"])
def qa_override(cr_id):
    data = request.get_json(silent=True) or {}
    c = db.session.get(ChangeRequest, cr_id)
    if not c: return jsonify({"error":"CR not found"}), 404
    old_dept, old_status = c.department, c.status
    if "department" in data: c.department = data["department"]
    if "status" in data: c.status = data["status"]
    if "ai_routing" in data: c.ai_routing = data["ai_routing"]
    db.session.commit()
    log_stage(c.id, "qa_override", f"QA override: dept {old_dept or '—'}→{c.department or '—'}, status {old_status}→{c.status}")
    return jsonify({"ok": True})

# routes_core.py (TEMP DEBUG ENDPOINT — remove later)
@core_bp.route("/_debug/dept_heads", methods=["GET"])
def debug_dept_heads():
    out = {}
    for u in User.query.filter_by(role="dept_head").all():
        d = db.session.get(Department, u.department_id)
        if d:
            out[d.name] = {"user_id": u.id, "name": u.name}
    return jsonify(out)

# --- NEW: per-CR SLA widget data
@core_bp.route("/cr/<int:cr_id>/sla", methods=["GET"])
def cr_sla(cr_id):
    c = db.session.get(ChangeRequest, cr_id)
    if not c: return jsonify({"error":"CR not found"}), 404
    return jsonify(compute_sla_for(c))

# --- NEW: rollup SLA summary for dashboard
@core_bp.route("/sla/summary", methods=["GET"])
def sla_summary():
    """
    Returns totals by state + simple 'AI time saved' estimate:
    We estimate manual routing latency of 24h; if AI put a CR directly into IN_REVIEW on submit,
    we count that as saved_hours for that CR.
    """
    from sqlalchemy import func
    crs = ChangeRequest.query.all()
    buckets = {"on_track":0, "amber":0, "breached":0, "n/a":0}
    saved_hours = 0.0

    for c in crs:
        m = compute_sla_for(c)
        buckets[m["state"]] = buckets.get(m["state"], 0) + 1
        # naive demo metric: if the CR moved to IN_REVIEW within 5 minutes of creation → assume 24h saved
        if c.status == "IN_REVIEW" and c.created_at and c.status_started_at:
            if (c.status_started_at - c.created_at).total_seconds() <= 5*60:
                saved_hours += 24.0

    total = len(crs)
    return jsonify({
        "total": total,
        "states": buckets,
        "ai_time_saved_hours_est": round(saved_hours, 1)
    })