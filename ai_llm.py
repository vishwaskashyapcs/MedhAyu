import os, json, time
from app import db
from models import Department, User, SOPItem, ChangeRequest
from openai import OpenAI
from dotenv import load_dotenv

from extensions import db         # <-- here
from sqlalchemy import case
from models import Department, User, SOPItem, ChangeRequest
load_dotenv()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = """You are “Pharma Change Control Assistant”.

For departments, you MUST return exactly one string copied verbatim from the provided `departments` list (no abbreviations like QA/QC; copy the full name exactly).
Return department as name; return owner_user_id as an integer user_id.

1) Read the Change Request (CR) text and produce:
   summary.problem[] (short bullets),
   summary.justification[] (short bullets),
   summary.impact[] (short bullets).

2) Using ONLY the provided context (departments, department_heads, SOP catalog):
   - match 1–3 relevant SOPs (if any) and return objects with:
       {"code": "<SOP code>", "owner_department": "<exact dept name from sop_catalog>"}
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
- For predicted_department, choose EXACTLY one value copied from the `departments` array provided in CONTEXT.
- Do NOT output abbreviations like "QA", "QC", "R&D", "Validation/CSV". Use the exact string (including spaces/slashes) from the list.
"""

# --- Normalization helpers ---
def _dept_maps():
    id_to_name = {}
    name_to_head = {}

    for d in db.session.query(Department).all():
        id_to_name[d.id] = d.name

    # accept dept_head OR qa as “head-like”
    head_roles = ["dept_head", "qa"]
    for u in db.session.query(User).filter(User.role.in_(head_roles)).all():
        d = db.session.get(Department, u.department_id)
        if d and d.name not in name_to_head:  # first match wins
            name_to_head[d.name] = u.id

    return id_to_name, name_to_head


import re

_ALIASES = {
    "qa": "Quality Assurance",
    "qualityassurance": "Quality Assurance",
    "qc": "Quality Control",
    "qualitycontrol": "Quality Control",
    "it": "IT Systems",
    "itsystems": "IT Systems",
    "regulatory": "Regulatory Affairs",
    "regulatoryaffairs": "Regulatory Affairs",
    "validationcsv": "Validation / CSV",
    "validation/ csv": "Validation / CSV",
    "validation/CSV".lower(): "Validation / CSV",
    "supplychain": "Supply Chain / Warehouse",
    "supplychain/warehouse": "Supply Chain / Warehouse",
    "ehs": "EHS",
    "engineering": "Engineering",
    "manufacturing": "Manufacturing",
    "rnd": "R&D / Formulation",
    "r&d": "R&D / Formulation",
    "r&d/formulation": "R&D / Formulation",
}

def _norm(s: str) -> str:
    # lower, remove all non-alphanum
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _coerce_department(value):
    if not value:
        return None

    # 1) exact / case-insensitive exact
    names = [d.name for d in db.session.query(Department).all()]
    lower_map = {n.lower(): n for n in names}
    v = str(value).strip()
    if v in names:
        return v
    if v.lower() in lower_map:
        return lower_map[v.lower()]

    # 2) normalization and aliasing
    norm_names = {_norm(n): n for n in names}
    vnorm = _norm(v)
    if vnorm in norm_names:
        return norm_names[vnorm]
    if vnorm in _ALIASES:
        return _ALIASES[vnorm]

    # 3) numeric id fallback
    try:
        n = int(v)
        id_to_name = {d.id: d.name for d in db.session.query(Department).all()}
        if n in id_to_name:
            return id_to_name[n]
    except Exception:
        pass

    return None

def _normalize_llm_result(data):
    _, name_to_head = _dept_maps()

    dept = data.get("predicted_department")
    norm_dept = _coerce_department(dept)
    if not norm_dept:
        # (existing SOP fallback…)
        # ...
        pass

    if not norm_dept:
        data["predicted_department"] = "Manual Review"
        data["owner_user_id"] = None
        data["owner_name"] = None
        return data

    data["predicted_department"] = norm_dept

    head_id = name_to_head.get(norm_dept)
    if not head_id:
        # fallback: pick someone in that department, preferring roles
        d = db.session.query(Department).filter_by(name=norm_dept).first()
        if d:
            role_priority = case(
                (User.role == "dept_head", 0),
                (User.role == "qa", 1),
                else_=2
            )
            cand = (db.session.query(User)
                    .filter(User.department_id == d.id)
                    .order_by(role_priority.asc(), User.id.asc())
                    .first())
            if cand:
                head_id = cand.id

    data["owner_user_id"] = head_id
    data["owner_name"] = (db.session.get(User, head_id).name if head_id else None)
    return data

def _fetch_context_for_prompt():
    departments = [d.name for d in db.session.query(Department).all()]

    dept_heads = {}
    for u in db.session.query(User).filter(User.role.in_(["dept_head", "qa"])).all():
        d = db.session.get(Department, u.department_id)
        if d and d.name not in dept_heads:
            dept_heads[d.name] = {"owner_user_id": u.id, "owner_name": u.name}

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

def _call_llm_json(system_prompt: str, user_prompt: str, temperature=0.2, retries=1):
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=temperature,
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            time.sleep(0.8)
    raise last_err

def _coerce_schema(data_raw, cr_description):
    fallback_summary = {
        "problem": [(cr_description or "")[:140]],
        "justification": [],
        "impact": []
    }
    if not isinstance(data_raw, dict):
        return {
            "summary": fallback_summary,
            "matched_sops": [],
            "predicted_department": "Manual Review",
            "owner_user_id": None,
            "rationale": "Invalid structure; manual review.",
            "confidence": 0.3
        }
    out = {
        "summary": data_raw.get("summary") or fallback_summary,
        "matched_sops": data_raw.get("matched_sops") or [],
        "predicted_department": data_raw.get("predicted_department") or "Manual Review",
        "owner_user_id": data_raw.get("owner_user_id"),
        "rationale": data_raw.get("rationale") or "",
        "confidence": 0.0
    }
    try:
        out["confidence"] = float(data_raw.get("confidence") or 0.0)
    except Exception:
        out["confidence"] = 0.0
    return out

def run_ai_for_cr(cr_id: int):
    cr = db.session.get(ChangeRequest, cr_id)
    if not cr:
        return None, "CR not found"

    prompt = _user_prompt(f"{cr.title}\n\n{cr.description or ''}")

    try:
        raw = _call_llm_json(SYSTEM_PROMPT, prompt, temperature=0.2, retries=1)
        data_raw = json.loads(raw)
    except Exception:
        data_raw = None

    data = _coerce_schema(data_raw, cr.description)
    data = _normalize_llm_result(data)
    # include owner_name for UI convenience
    owner_name = None
    if data.get("owner_user_id"):
        u = db.session.get(User, data["owner_user_id"])
        owner_name = u.name if u else None

    # persist on CR
    cr.ai_summary = data.get("summary")
    cr.ai_routing = {
        "matched_sops": data.get("matched_sops", []),
        "predicted_department": data.get("predicted_department"),
        "owner_user_id": data.get("owner_user_id"),
        "rationale": data.get("rationale"),
        "confidence": data.get("confidence", 0.0)
    }

    # status gating by confidence (uses env knob CONFIDENCE_THRESHOLD or 0.6 default)
    conf_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    dept = data.get("predicted_department")
    conf = float(data.get("confidence") or 0.0)
    if dept and dept != "Manual Review" and conf >= conf_threshold:
        cr.department = dept
        cr.status = "IN_REVIEW"
    else:
        cr.status = "NEW"

    db.session.commit()

    # return payload for UI
    out = dict(data)
    out["owner_name"] = owner_name
    return out, None


