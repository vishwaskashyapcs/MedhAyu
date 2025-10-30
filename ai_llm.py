# ai_llm.py
import os, json
from app import db
from models import Department, User, SOPItem, ChangeRequest

# ---- Choose your model provider ----
# OpenAI (example):
from openai import OpenAI
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are “Pharma Change Control Assistant”.

1) Read the Change Request (CR) text and produce:
   summary.problem[] (short bullets),
   summary.justification[] (short bullets),
   summary.impact[] (short bullets).

2) Using ONLY the provided context (departments, department_heads, SOP catalog):
   - match 1–3 relevant SOP codes (if any),
   - select exactly one predicted_department from the list,
   - set owner_user_id = the department head’s user_id for that department,
   - provide a short rationale citing phrases from CR or SOP snippets,
   - set confidence 0.0–1.0.

3) Output ONLY JSON with this schema:
{
  "summary": { "problem": [], "justification": [], "impact": [] },
  "matched_sops": [],
  "predicted_department": "",
  "owner_user_id": null,
  "rationale": "",
  "confidence": 0.0
}

Rules:
- Use provided departments/users/SOPs; do not invent.
- If uncertain, use "Manual Review", owner_user_id = null, confidence <= 0.5.
- Be concise and deterministic.
"""

def _fetch_context_for_prompt():
    # departments
    departments = [d.name for d in db.session.query(Department).all()]

    # dept -> head (from users table)
    dept_heads = {}
    for u in db.session.query(User).all():
        if u.role == "dept_head":
            d = db.session.get(Department, u.department_id)
            if d:
                dept_heads[d.name] = {"owner_user_id": u.id, "owner_name": u.name}

    # compact SOP catalog
    sops = []
    for s in db.session.query(SOPItem).all():
        sops.append({
            "code": s.code,
            "title": s.title,
            "snippet": (s.content_snippet or "")[:240],
            "owner_department": s.owner_department
        })
    return departments, dept_heads, sops

def _user_prompt(cr_text: str) -> str:
    departments, dept_heads, sops = _fetch_context_for_prompt()
    return (
        "CONTEXT:\n"
        f"departments: {json.dumps(departments, ensure_ascii=False)}\n"
        f"department_heads: {json.dumps(dept_heads, ensure_ascii=False)}\n"
        f"sop_catalog: {json.dumps(sops, ensure_ascii=False)}\n\n"
        f"CR_TEXT:\n{cr_text}\n\n"
        "Return ONLY JSON (no markdown, no commentary)."
    )

def call_llm(system_prompt: str, user_prompt: str) -> str:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":user_prompt}
        ],
        response_format={"type": "json_object"}  # enforces JSON
    )
    return resp.choices[0].message.content

def run_ai_for_cr(cr_id: int):
    cr = db.session.get(ChangeRequest, cr_id)
    if not cr:
        return None, "CR not found"

    user_prompt = _user_prompt(f"{cr.title}\n\n{cr.description or ''}")
    raw = call_llm(SYSTEM_PROMPT, user_prompt)

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "summary":{"problem":[(cr.description or "")[:140]],"justification":[],"impact":[]},
            "matched_sops":[],
            "predicted_department":"Manual Review",
            "owner_user_id": None,
            "rationale":"Model returned invalid JSON. Flagged for manual review.",
            "confidence": 0.3
        }

    # persist
    cr.ai_summary = data.get("summary")
    cr.ai_routing = {
        "matched_sops": data.get("matched_sops", []),
        "predicted_department": data.get("predicted_department"),
        "owner_user_id": data.get("owner_user_id"),
        "rationale": data.get("rationale"),
        "confidence": data.get("confidence", 0.0)
    }

    # status update: confident → move to IN_REVIEW
    dept = data.get("predicted_department")
    conf = float(data.get("confidence") or 0)
    if dept and dept != "Manual Review" and conf >= 0.6:
        cr.department = dept
        cr.status = "IN_REVIEW"
    else:
        cr.status = "NEW"  # or "NEEDS_TRIAGE"

    db.session.commit()
    return data, None
