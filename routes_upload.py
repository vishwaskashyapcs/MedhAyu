# routes_upload.py
import re
from io import BytesIO
from flask import Blueprint, request, jsonify, Response
from extensions import db
from models import ChangeRequest
from ai_llm import run_ai_for_cr
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

upload_bp = Blueprint("upload_bp", __name__)

# ---------- 1) Fixed-format template ----------
TEMPLATE_TEXT = """CR TITLE: <enter concise title here>
DECLARED DEPARTMENT: <exact department name from the dropdown list, e.g., Manufacturing>
RISK: <Minor|Moderate|Major>  (optional)

DESCRIPTION:
<free text — multiple lines allowed. Put the detailed CR description here.>
"""

@upload_bp.route("/upload/template.pdf", methods=["GET"])
def upload_template_pdf():
    """
    Returns a downloadable PDF that shows the fixed-format template
    users should follow when preparing CR files.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    width, height = A4
    x_left = 20 * mm
    y = height - 20 * mm
    line_gap = 8 * mm

    def write(line, bold=False):
        nonlocal y
        if bold:
            c.setFont("Helvetica-Bold", 12)
        else:
            c.setFont("Helvetica", 11)
        c.drawString(x_left, y, line)
        y -= line_gap

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x_left, y, "Change Request (CR) — Fixed Format Template")
    y -= 12 * mm

    # Body
    write("Follow this structure exactly (order can vary). Save as .txt and upload.", False)
    y -= 4 * mm
    write("CR TITLE: <enter concise title here>", True)
    write("DECLARED DEPARTMENT: <exact department name (e.g., Manufacturing)>", True)
    write("RISK: <Minor|Moderate|Major>  (optional)", True)
    y -= 4 * mm
    write("DESCRIPTION:", True)
    write("<free text — multiple lines allowed. Put the detailed CR description here.>", False)

    # Light footer
    y -= 8 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(x_left, y, "Tip: You can also download a plain text version at /upload/template.txt")

    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="CR_template.pdf"'}
    )

@upload_bp.route("/upload/template.txt", methods=["GET"])
def upload_template_txt():
    return Response(TEMPLATE_TEXT, mimetype="text/plain; charset=utf-8")

# ---------- 2) Parser helpers ----------
_FIELD_PATTERNS = {
    "title": re.compile(r"^\s*(?:CR\s*TITLE|TITLE)\s*:\s*(.+)$", re.I),
    "department": re.compile(r"^\s*(?:DECLARED\s*DEPARTMENT|DEPARTMENT)\s*:\s*(.+)$", re.I),
    "risk": re.compile(r"^\s*RISK\s*:\s*(.+)$", re.I),
    "description_hdr": re.compile(r"^\s*DESCRIPTION\s*:\s*$", re.I),
}

def _bytes_to_text(b: bytes) -> str:
    # Keep it robust for .txt; (docx/pdf handled separately if you want later)
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="ignore")

def _parse_fixed_format(text: str) -> dict:
    """
    Expected minimal format (order can vary):

    CR TITLE: ...
    DECLARED DEPARTMENT: ...
    RISK: Minor|Moderate|Major   (optional)

    DESCRIPTION:
    multi-line free text...
    """
    title = department = risk = None
    description = []
    in_desc = False

    for raw in text.splitlines():
        line = raw.rstrip("\n")

        if not in_desc:
            m = _FIELD_PATTERNS["title"].match(line)
            if m:
                title = m.group(1).strip()
                continue
            m = _FIELD_PATTERNS["department"].match(line)
            if m:
                department = m.group(1).strip()
                continue
            m = _FIELD_PATTERNS["risk"].match(line)
            if m:
                risk = m.group(1).strip()
                continue
            if _FIELD_PATTERNS["description_hdr"].match(line):
                in_desc = True
                continue
        else:
            description.append(line)

    return {
        "title": (title or "").strip(),
        "department": (department or "").strip(),
        "risk": (risk or "").strip(),
        "description": "\n".join(description).strip(),
    }

# ---------- 3) Upload & extract endpoint ----------
@upload_bp.route("/upload/parse", methods=["POST"])
def upload_parse():
    """
    Accepts: multipart form-data
      - file: .txt (preferred)
      - auto_run_ai: "1" to immediately run AI, else "0" (default)

    Returns: {
      "cr_id": <int>,
      "status": "NEW" | "IN_REVIEW" | ...,
      "parsed": {title, department, risk, description},
      "ai": {...}   # only when auto_run_ai=1 and LLM succeeds
    }
    """
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file uploaded."}), 400

    auto_run = (request.form.get("auto_run_ai") == "1")

    # NOTE: This implementation focuses on .txt (simple & reliable).
    # If you later want .docx/.pdf, convert them to text first.
    try:
        raw = f.read()
        text = _bytes_to_text(raw)
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {e}"}), 400

    parsed = _parse_fixed_format(text)

    if not parsed.get("description"):
        return jsonify({"error": "Template parse failed. Make sure the file follows the template and includes a DESCRIPTION: block."}), 400

    # Create CR using parsed fields (title optional)
    cr = ChangeRequest(
        title=parsed.get("title") or "",
        description=parsed.get("description") or "",
        department=parsed.get("department") or None,
        risk=parsed.get("risk") or None,
        status="NEW",
    )
    db.session.add(cr)
    db.session.commit()

    out = {"cr_id": cr.id, "status": cr.status, "parsed": parsed}

    if auto_run:
        data, err = run_ai_for_cr(cr.id)
        if not err and data:
            out["ai"] = {
                "summary": data.get("summary"),
                "matched_sops": data.get("matched_sops"),
                "predicted_department": data.get("predicted_department"),
                "owner_user_id": data.get("owner_user_id"),
                "owner_name": data.get("owner_name"),
                "rationale": data.get("rationale"),
                "confidence": data.get("confidence"),
            }

    return jsonify(out), 200
