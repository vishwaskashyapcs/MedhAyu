

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
    # auth: only Quality Control users
    user_id = request.args.get("user_id", type=int) or request.headers.get("X-User-Id", type=int)
    if not user_id or not _can_see_super_admin(user_id):
        return jsonify({"error": "forbidden"}), 403

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
    # auth: only Quality Control users
    user_id = request.args.get("user_id", type=int) or request.headers.get("X-User-Id", type=int)
    if not user_id or not _can_see_super_admin(user_id):
        return jsonify({"error": "forbidden"}), 403

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

@core_bp.route("/cr/<int:cr_id>/sla", methods=["GET"])
def cr_sla(cr_id):
    from utils_benchmark import estimate_manual_baseline_for
    from utils_sla import compute_sla_for

    c = db.session.get(ChangeRequest, cr_id)
    if not c:
        return jsonify({"error": "CR not found"}), 404

    # SLA and time tracking
    sla_data = compute_sla_for(c)

    # manual baseline from history or heuristic
    baseline_h, source, detail = estimate_manual_baseline_for(c)

    # actual AI runtime in hours (from ai_elapsed_seconds)
    ai_hours = round((c.ai_elapsed_seconds or 0) / 3600.0, 3)

    # SLA target (from policy table)
    sla_target_h = None
    try:
        from models import SLA
        policy = SLA.query.filter_by(status=c.status).first()
        sla_target_h = float(policy.sla_hours) if policy else None
    except Exception:
        sla_target_h = None

    # compute savings
    time_saved = None
    pct_saved = None
    if baseline_h and ai_hours > 0:
        time_saved = max(0.0, baseline_h - ai_hours)
        pct_saved = round((time_saved / baseline_h) * 100.0, 1)

    # enrich SLA data
    sla_data.update({
        "manual_baseline_h": round(baseline_h, 2) if baseline_h else None,
        "baseline_source": source,
        "ai_elapsed_h": ai_hours,
        "sla_target_h": sla_target_h,
        "time_saved_h": round(time_saved, 2) if time_saved else None,
        "time_saved_pct": pct_saved,
        "baseline_detail": detail
    })
    return jsonify(sla_data)


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

# --- helper: is this user allowed to see the Super Admin (QA) board?
def _can_see_super_admin(user_id: int) -> bool:
    u = db.session.get(User, user_id)
    if not u:
        return False
    d = db.session.get(Department, u.department_id)
    # Only users from the "Quality Control" department are allowed
    return bool(d and d.name == "Quality Control")

# --- probe endpoint the UI can call to decide whether to show the QA board
@core_bp.route("/auth/can_see_qa/<int:user_id>", methods=["GET"])
def can_see_qa(user_id):
    if _can_see_super_admin(user_id):
        return jsonify({"ok": True})
    return jsonify({"error": "forbidden"}), 403



# routes_core.py (add imports at top if not already present)
from flask import send_file, jsonify
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether
import tempfile, os

# --- NEW: robust, readable word cloud helper ---
def _make_wordcloud_image(text: str) -> str | None:
    """Return path to a temporary PNG wordcloud image (or None if no text)."""
    text = (text or "").strip()
    if not text:
        return None

    # Headless backend (no X server required)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from wordcloud import WordCloud, STOPWORDS

    # Build stopword set (tune to your domain)
    extra_stops = {
        "the","and","for","with","of","to","in","on","by","a","an","is","are",
        "this","that","it","as","be","or","from","at","per","etc",
        # domain-ish noise
        "change","request","cr","sop","update","updated","revise","revision",
        "policy","procedure","process","department","team","plant","line",
        "document","section","impact","justification","problem"
    }
    stops = STOPWORDS.union(extra_stops)

    # High-res canvas for print
    width, height = 1200, 600
    wc = WordCloud(
        width=width,
        height=height,
        background_color="white",
        stopwords=stops,
        collocations=False,           # show single tokens only
        normalize_plurals=True,
        prefer_horizontal=1.0,
        max_words=200,
        min_font_size=10,
        max_font_size=150,
        margin=2,
    ).generate(text)

    # Render to temp PNG
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    plt.figure(figsize=(width/200, height/200), dpi=200)  # 200 DPI output
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(tmp.name, dpi=200)
    plt.close()
    return tmp.name


@core_bp.route("/cr/<int:cr_id>/pdf")
def cr_pdf(cr_id):
    from models import ChangeRequest
    cr = db.session.get(ChangeRequest, cr_id)
    if not cr:
        return jsonify({"error": "CR not found"}), 404

    ai = cr.ai_routing or {}
    summary = ai.get("summary") or {}
    desc = cr.description or ""
    word_count = len(desc.split())

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=36, rightMargin=36, topMargin=40, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    def p(label, text, style="BodyText"):
        story.append(Paragraph(f"<b>{label}:</b> {text}", styles[style]))
        story.append(Spacer(1, 8))

    story.append(Paragraph(f"Change Request #{cr.id} — {cr.title or '(Untitled)'}", styles["Title"]))
    story.append(Spacer(1, 10))
    p("Status", cr.status or "—", "Normal")

    def bullets(heading, items):
        items = [i for i in (items or []) if i]
        story.append(Paragraph(f"<b>{heading}</b>", styles["Heading4"]))
        if items:
            for i in items:
                story.append(Paragraph(f"• {i}", styles["BodyText"]))
        else:
            story.append(Paragraph("—", styles["BodyText"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 6))
    bullets("Problem",       summary.get("problem"))
    bullets("Justification", summary.get("justification"))
    bullets("Impact",        summary.get("impact"))

    # Textual Word Cloud
    terms = _top_terms(desc, n=15)
    story.append(Paragraph("Word Cloud", styles["Heading4"]))
    if terms:
        wc_line = ", ".join(f"{w} ({c})" for w, c in terms)
        story.append(Paragraph(wc_line, styles["BodyText"]))
    else:
        story.append(Paragraph("—", styles["BodyText"]))
    story.append(Spacer(1, 10))

    # Routing
    story.append(Paragraph("Routing", styles["Heading4"]))
    p("Predicted Dept", ai.get("predicted_department", "—"))
    owner_name = ai.get("owner_name") or "—"
    owner_id = ai.get("owner_user_id")
    owner_text = owner_name if not owner_id else f"{owner_name} (id {owner_id})"
    p("Owner", owner_text)
    matched = ai.get("matched_sops") or []
    sop_codes = []
    for s in matched:
        sop_codes.append(s.get("code") if isinstance(s, dict) else str(s))
    sop_codes = [c for c in sop_codes if c]
    p("Matched SOPs", ", ".join(sop_codes) if sop_codes else "—")
    p("Rationale", ai.get("rationale", "—"))

    # Word Count (plain line)
    p("Word Count (CR Description)", str(word_count), "Normal")

    doc.build(story)
    buffer.seek(0)

    return send_file(buffer, mimetype="application/pdf",
                     as_attachment=True, download_name=f"CR_{cr.id}.pdf")

from collections import Counter
import re
from wordcloud import STOPWORDS  # just using its stopword set

# ---- textual "word cloud" (top terms) ----
def _top_terms(text: str, n: int = 15):
    """
    Return list of (term, count) from text with stopwords removed.
    No images; purely textual frequencies.
    """
    extra_stops = {
        "the","and","for","with","of","to","in","on","by","a","an","is","are",
        "this","that","it","as","be","or","from","at","per","etc",
        # domain noise
        "change","request","cr","sop","update","updated","revise","revision",
        "policy","procedure","process","department","team","plant","line",
        "document","section","impact","justification","problem"
    }
    stops = set(STOPWORDS) | extra_stops

    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", (text or "").lower())
    tokens = [t for t in tokens if t not in stops and len(t) > 2]
    counts = Counter(tokens)
    return counts.most_common(n)



from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
from io import BytesIO
import os, re

# Optional parsers (fine if missing; we fall back to plain text)
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:
    pdf_extract_text = None

try:
    import docx  # python-docx
except Exception:
    docx = None

def _extract_text_from_upload(file_storage):
    """Return plain text from .txt/.pdf/.docx; fallback to bytes->utf-8."""
    if not file_storage:
        return ""
    filename = secure_filename(file_storage.filename or "")
    ext = os.path.splitext(filename.lower())[1]
    data = file_storage.read()  # bytes

    if ext == ".txt":
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("latin-1", errors="ignore")

    if ext == ".pdf" and pdf_extract_text:
        try:
            return pdf_extract_text(BytesIO(data)) or ""
        except Exception:
            return ""

    if ext == ".docx" and docx:
        try:
            doc = docx.Document(BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text) or ""
        except Exception:
            return ""

    # Fallback
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return data.decode("latin-1", errors="ignore")

_DEPT_KEYS = [
    "Manufacturing", "Quality Assurance", "Quality Control", "Engineering",
    "Validation / CSV", "IT Systems", "Regulatory Affairs",
    "Supply Chain / Warehouse", "EHS", "R&D / Formulation"
]

def _parse_title_desc_dept(full_text: str):
    """Heuristic parse for title/description/department."""
    text = (full_text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Department line (Department: <name>)
    dept = None
    for ln in lines[:8]:
        m = re.search(r"^(dept|department)\s*:\s*(.+)$", ln, flags=re.I)
        if m:
            guess = m.group(2).strip()
            for d in _DEPT_KEYS:
                if d.lower() == guess.lower() or guess.lower() in d.lower():
                    dept = d
                    break
            break

    # Title = first non-empty line that is not a Dept label
    title = ""
    for ln in lines:
        if re.match(r"^(dept|department)\s*:", ln, flags=re.I):
            continue
        title = ln[:120].strip()
        break

    desc_lines, used = [], False
    for ln in lines:
        if not used and ln == title:
            used = True
            continue
        desc_lines.append(ln)
    description = "\n".join(desc_lines).strip()

    if not dept:
        lower_all = text.lower()
        for d in _DEPT_KEYS:
            if d.lower() in lower_all:
                dept = d
                break

    return {"title": title, "description": description, "declared_department": (dept or "")}

@core_bp.route("/upload/extract", methods=["POST"])
def upload_extract():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file received"}), 400
    txt = _extract_text_from_upload(f)
    out = _parse_title_desc_dept(txt)
    return jsonify(out), 200

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

@core_bp.route("/upload/template", methods=["GET"])
def upload_template_pdf():
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=40, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("Change Request — Fixed Format Template", styles["Title"]))
    story.append(Spacer(1, 12))
    for label, hint in [
        ("Department:", "(e.g., Manufacturing / Quality Assurance / IT Systems …)"),
        ("Title:", "(brief)"),
        ("Problem:", "(bullets allowed)"),
        ("Justification:", ""),
        ("Impact:", ""),
        ("Details:", "(full description)"),
    ]:
        story.append(Paragraph(f"<b>{label}</b> {hint}", styles["BodyText"]))
        story.append(Spacer(1, 10))
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name="CR_fixed_template.pdf")


# --- QA summary report (CSV download)
from io import StringIO
import csv
from flask import send_file, make_response
from datetime import datetime
from collections import defaultdict

@core_bp.route("/reports/qa-summary", methods=["GET"])
def qa_summary_report():
    from models import ChangeRequest, Department, SLA, CRLog

    # Pull all data
    crs = ChangeRequest.query.order_by(ChangeRequest.id.asc()).all()
    depts = {d.id: d.name for d in Department.query.all()}

    # SLA lookup (status -> hours)
    sla_map = {s.status: int(s.sla_hours or 0) for s in SLA.query.all()}

    # Per-department aggregation
    per_dept = defaultdict(lambda: {"TOTAL": 0, "NEW": 0, "IN_REVIEW": 0, "QA_REVIEW": 0, "IMPLEMENTED": 0, "CLOSED": 0})
    total_closed = 0
    total_est_hours = 0

    # Build a “flat” table of CRs with a few columns
    flat_rows = []
    for c in crs:
        dept = c.department or ""
        per_dept[dept]["TOTAL"] += 1
        per_dept[dept][c.status] += 1
        if c.status == "CLOSED":
            total_closed += 1

        est = sla_map.get(c.status, 0)
        total_est_hours += est

        # first/last log times (if CRLog model is present)
        first_log = CRLog.query.filter_by(cr_id=c.id).order_by(CRLog.ts.asc()).first()
        last_log  = CRLog.query.filter_by(cr_id=c.id).order_by(CRLog.ts.desc()).first()
        first_ts = first_log.ts.isoformat() if first_log else ""
        last_ts  = last_log.ts.isoformat() if last_log else ""

        flat_rows.append([
            c.id, c.title or "", dept, c.status, est,
            (c.ai_routing or {}).get("predicted_department", ""),
            (c.ai_routing or {}).get("owner_user_id", ""),
            (c.ai_routing or {}).get("rationale", ""),
            first_ts, last_ts
        ])

    # Render CSV in-memory
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["QA SUMMARY REPORT", datetime.utcnow().isoformat()])
    w.writerow([])
    w.writerow(["Totals"])
    w.writerow(["Total CRs", len(crs)])
    w.writerow(["Total Closed", total_closed])
    w.writerow(["Estimated Hours (sum by status)", total_est_hours])
    w.writerow([])

    w.writerow(["Per-Department"])
    w.writerow(["Department","TOTAL","NEW","IN_REVIEW","QA_REVIEW","IMPLEMENTED","CLOSED"])
    for dept, agg in sorted(per_dept.items()):
        w.writerow([dept or "(Unassigned)",
                    agg["TOTAL"], agg["NEW"], agg["IN_REVIEW"], agg["QA_REVIEW"], agg["IMPLEMENTED"], agg["CLOSED"]])
    w.writerow([])

    w.writerow(["All Change Requests"])
    w.writerow(["CR ID","Title","Department","Status","Est. Hours",
               "AI Predicted Dept","Owner User ID","AI Rationale","First Log","Last Log"])
    w.writerows(flat_rows)

    csv_data = buf.getvalue().encode("utf-8")
    resp = make_response(csv_data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = 'attachment; filename="qa_summary_report.csv"'
    return resp
