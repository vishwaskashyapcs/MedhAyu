import os, json, time
from app import db
from models import Department, User, SOPItem, ChangeRequest
from openai import OpenAI
from dotenv import load_dotenv

from extensions import db         # <-- here
from models import Department, User, SOPItem, ChangeRequest
load_dotenv()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = """You are “Pharma Change Control Assistant”.

Return fields as NAMES, not numeric IDs. For departments, return the exact department name from CONTEXT.

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

# --- Normalization helpers ---
def _dept_maps():
    # id -> name and name -> head user_id
    id_to_name = {}
    name_to_head = {}
    for d in db.session.query(Department).all():
        id_to_name[d.id] = d.name
    for u in db.session.query(User).filter(User.role=="dept_head").all():
        d = db.session.get(Department, u.department_id)
        if d:
            name_to_head[d.name] = u.id
    return id_to_name, name_to_head

def _coerce_department(value):
    """
    Accepts: exact name, case-insensitive name, numeric id string, or index-like "0".
    Returns a valid department name or None.
    """
    if not value:
        return None
    id_to_name, _ = _dept_maps()

    # if numeric-like -> try dept id
    try:
        n = int(str(value).strip())
        if n in id_to_name:
            return id_to_name[n]
    except Exception:
        pass

    # try exact/case-insensitive match
    names = [d.name for d in db.session.query(Department).all()]
    lower_map = {n.lower(): n for n in names}
    v = str(value).strip()
    if v in names:
        return v
    if v.lower() in lower_map:
        return lower_map[v.lower()]
    return None

def _normalize_llm_result(data):
    """Force department to a valid name and owner to real dept head; fill owner_name."""
    id_to_name, name_to_head = _dept_maps()

    dept = data.get("predicted_department")
    norm_dept = _coerce_department(dept)
    if not norm_dept:
        # fallback from matched_sops owner_department if present
        sops = data.get("matched_sops") or []
        # if list of dicts -> check owner_department; if list of codes -> leave as is
        norm_dept = None
        try:
            for s in sops:
                if isinstance(s, dict) and s.get("owner_department"):
                    cand = _coerce_department(s["owner_department"])
                    if cand: 
                        norm_dept = cand
                        break
        except Exception:
            pass

    if not norm_dept:
        data["predicted_department"] = "Manual Review"
        data["owner_user_id"] = None
        data["owner_name"] = None
        return data

    data["predicted_department"] = norm_dept

    # Force owner to the dept head
    head_id = name_to_head.get(norm_dept)
    data["owner_user_id"] = head_id
    data["owner_name"] = (db.session.get(User, head_id).name if head_id else None)
    return data

def _fetch_context_for_prompt():
    departments = [d.name for d in db.session.query(Department).all()]

    dept_heads = {}
    for u in db.session.query(User).all():
        if u.role == "dept_head":
            d = db.session.get(Department, u.department_id)
            if d:
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


