

# utils_benchmark.py
from statistics import median
from typing import Optional, Tuple, Dict, Any
from extensions import db
from models import ChangeRequest, CRStatusHistory
from datetime import timezone
import re

# --- Dept-specific review speed defaults (minutes per 200 words) ---
# Calibrated “QA manual read-and-route” rates per department.
# Tweak these to match your datasets.
DEPT_RATES_MIN_PER_200W = {
    "Quality Assurance": 18,
    "Quality Control": 16,
    "Manufacturing": 14,
    "Engineering": 14,
    "Validation / CSV": 22,
    "IT Systems": 16,
    "Regulatory Affairs": 24,
    "Supply Chain / Warehouse": 12,
    "EHS": 18,
    "R&D / Formulation": 20,
    # Fallback
    "*": 18,
}

# Fixed overhead (minutes) — opening CR, scanning metadata, filing, etc.
FIXED_OVERHEAD_MIN = 6

def _coerce_hours(val) -> Optional[float]:
    try:
        f = float(val)
        return f if f > 0 else None
    except Exception:
        return None

def _median_safe(values):
    v = [x for x in values if x is not None]
    return median(v) if v else None

def _dur_hours(a, b) -> Optional[float]:
    if not a or not b:
        return None
    if a.tzinfo is None: a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None: b = b.replace(tzinfo=timezone.utc)
    return max(0.0, (b - a).total_seconds() / 3600.0)

def _word_count(s: str) -> int:
    if not s:
        return 0
    # Count tokens similar to a whitespace split but robust to punctuation
    return len(re.findall(r"\w+", s))

def _dept_rate_min_per_200w(dept: Optional[str]) -> int:
    if not dept:
        return DEPT_RATES_MIN_PER_200W["*"]
    return DEPT_RATES_MIN_PER_200W.get(dept, DEPT_RATES_MIN_PER_200W["*"])

def _heuristic_from_text(dept: Optional[str], title: str, description: str) -> Dict[str, Any]:
    """
    Estimate manual baseline from the amount of text, using dept-specific read rates.
    Returns {hours, source, detail:{words, rate_min_per_200w, fixed_overhead_min}}
    """
    words = _word_count(f"{title or ''} {description or ''}")
    rate = _dept_rate_min_per_200w(dept)
    minutes = FIXED_OVERHEAD_MIN + (rate * (words / 200.0))
    hours = round(minutes / 60.0, 2)
    return {
        "hours": hours,
        "source": "heuristic_words_dept",
        "detail": {
            "words": words,
            "rate_min_per_200w": rate,
            "fixed_overhead_min": FIXED_OVERHEAD_MIN
        }
    }

def estimate_manual_baseline_for(cr: ChangeRequest) -> Tuple[Optional[float], str, Dict[str, Any]]:
    """
    Returns (hours, source, detail).
    source is one of:
      - "cr.manual_baseline_hours"
      - "dept_median_manual_baseline"
      - "dept_median_cycle_time"
      - "global_median_manual_baseline"
      - "global_median_cycle_time"
      - "heuristic_words_dept"
      - "unknown"
    detail may include {"words", "rate_min_per_200w", "fixed_overhead_min"} when heuristic applies.
    Priority:
      CR override -> dept median (manual) -> dept cycle-time median
      -> global median (manual) -> global cycle-time median
      -> words-based heuristic -> unknown
    """
    # 0) explicit on the CR
    if _coerce_hours(cr.manual_baseline_hours):
        return float(cr.manual_baseline_hours), "cr.manual_baseline_hours", {}

    # 1) department-scoped medians from stored manual_baseline_hours
    q = (db.session.query(ChangeRequest)
         .filter(ChangeRequest.department == cr.department)
         .filter(ChangeRequest.manual_baseline_hours.isnot(None)))
    dept_manual = _median_safe([_coerce_hours(x.manual_baseline_hours) for x in q])
    if dept_manual:
        return dept_manual, "dept_median_manual_baseline", {}

    # 2) department-scoped cycle-time medians (NEW → QA_REVIEW|IMPLEMENTED|CLOSED)
    crs_dept = db.session.query(ChangeRequest).filter(ChangeRequest.department == cr.department).all()
    durations = []
    for r in crs_dept:
        h = (db.session.query(CRStatusHistory)
             .filter(CRStatusHistory.cr_id == r.id)
             .order_by(CRStatusHistory.changed_at.asc())
             .all())
        t_new = next((x.changed_at for x in h if x.to_status == "NEW"), r.created_at)
        t_end = next((x.changed_at for x in h if x.to_status in ("QA_REVIEW","IMPLEMENTED","CLOSED")), None)
        durations.append(_dur_hours(t_new, t_end))
    dept_cycle = _median_safe(durations)
    if dept_cycle:
        return dept_cycle, "dept_median_cycle_time", {}

    # 3) global medians from manual_baseline_hours
    qg = db.session.query(ChangeRequest).filter(ChangeRequest.manual_baseline_hours.isnot(None))
    glob_manual = _median_safe([_coerce_hours(x.manual_baseline_hours) for x in qg])
    if glob_manual:
        return glob_manual, "global_median_manual_baseline", {}

    # 4) global cycle-time median
    all_crs = db.session.query(ChangeRequest).all()
    durations = []
    for r in all_crs:
        h = (db.session.query(CRStatusHistory)
             .filter(CRStatusHistory.cr_id == r.id)
             .order_by(CRStatusHistory.changed_at.asc())
             .all())
        t_new = next((x.changed_at for x in h if x.to_status == "NEW"), r.created_at)
        t_end = next((x.changed_at for x in h if x.to_status in ("QA_REVIEW","IMPLEMENTED","CLOSED")), None)
        durations.append(_dur_hours(t_new, t_end))
    glob_cycle = _median_safe(durations)
    if glob_cycle:
        return glob_cycle, "global_median_cycle_time", {}

    # 5) words-based heuristic (last resort before unknown)
    h = _heuristic_from_text(cr.department, cr.title or "", cr.description or "")
    if h["hours"] and h["hours"] > 0:
        return h["hours"], h["source"], h["detail"]

    # 6) unknown
    return None, "unknown", {}
