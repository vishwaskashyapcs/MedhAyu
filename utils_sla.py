# # utils_sla.py
# from datetime import datetime, timedelta, timezone
# from extensions import db
# from models import SLA, ChangeRequest, CRStatusHistory, CRLog

# def utcnow():
#     return datetime.now(timezone.utc)

# def _policy_map():
#     rows = SLA.query.all()
#     return {r.status: {"sla_h": int(r.sla_hours or 0),
#                        "amber_h": int(r.amber_threshold_hours or 0)} for r in rows}

# def compute_sla_for(cr: ChangeRequest):
#     """
#     Returns dict with countdowns & breach state based on current status
#     ({state: on_track|amber|breached}, due_at, amber_at, elapsed_h, remaining_h).
#     For terminal states (IMPLEMENTED/CLOSED) we mark 'n/a'.
#     """
#     terminals = {"IMPLEMENTED", "CLOSED"}
#     if cr.status in terminals or not cr.status_started_at:
#         return {
#             "status": cr.status,
#             "state": "n/a",
#             "started_at": cr.status_started_at.isoformat() if cr.status_started_at else None,
#             "due_at": None, "amber_at": None,
#             "elapsed_h": None, "remaining_h": None
#         }

#     pmap = _policy_map()
#     pol = pmap.get(cr.status, {"sla_h": 0, "amber_h": 0})
#     start = cr.status_started_at
#     due_at = start + timedelta(hours=pol["sla_h"])
#     amber_at = start + timedelta(hours=pol["amber_h"])
#     now = utcnow()

#     elapsed = (now - start).total_seconds() / 3600.0
#     remaining = (due_at - now).total_seconds() / 3600.0

#     if now > due_at:
#         state = "breached"
#     elif now > amber_at:
#         state = "amber"
#     else:
#         state = "on_track"

#     return {
#         "status": cr.status,
#         "state": state,
#         "started_at": start.isoformat(),
#         "due_at": due_at.isoformat(),
#         "amber_at": amber_at.isoformat(),
#         "elapsed_h": round(elapsed, 2),
#         "remaining_h": round(remaining, 2)
#     }

# def set_status(cr: ChangeRequest, new_status: str, note: str = ""):
#     """Single source of truth for status transitions: logs + history + SLA start."""
#     from_status = cr.status or "NEW"
#     cr.status = new_status
#     cr.status_started_at = utcnow()
#     db.session.add(CRStatusHistory(cr_id=cr.id, from_status=from_status, to_status=new_status, note=note))
#     db.session.add(CRLog(cr_id=cr.id, stage="status", message=f"{from_status} → {new_status}", level="info"))
#     db.session.commit()

# utils_sla.py
from datetime import datetime, timedelta, timezone
from extensions import db
from models import SLA, ChangeRequest, CRStatusHistory, CRLog

def utcnow():
    return datetime.now(timezone.utc)

def _aware(dt):
    """Coerce any datetime to UTC-aware (assume naive as UTC)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

def _policy_map():
    rows = SLA.query.all()
    return {r.status: {"sla_h": int(r.sla_hours or 0),
                       "amber_h": int(r.amber_threshold_hours or 0)} for r in rows}

def compute_sla_for(cr: ChangeRequest):
    """
    Returns dict with countdowns & breach state based on current status
    ({state: on_track|amber|breached}, due_at, amber_at, elapsed_h, remaining_h).
    For terminal states (IMPLEMENTED/CLOSED) we mark 'n/a'.
    """
    terminals = {"IMPLEMENTED", "CLOSED"}
    start = _aware(cr.status_started_at)

    if cr.status in terminals or not start:
        return {
            "status": cr.status,
            "state": "n/a",
            "started_at": start.astimezone(timezone.utc).isoformat() if start else None,
            "due_at": None, "amber_at": None,
            "elapsed_h": None, "remaining_h": None
        }

    pmap = _policy_map()
    pol = pmap.get(cr.status, {"sla_h": 0, "amber_h": 0})
    due_at = start + timedelta(hours=pol["sla_h"])
    amber_at = start + timedelta(hours=pol["amber_h"])
    now = utcnow()  # aware

    elapsed = (now - start).total_seconds() / 3600.0
    remaining = (due_at - now).total_seconds() / 3600.0

    if now > due_at:
        state = "breached"
    elif now > amber_at:
        state = "amber"
    else:
        state = "on_track"

    return {
        "status": cr.status,
        "state": state,
        "started_at": start.astimezone(timezone.utc).isoformat(),
        "due_at": due_at.astimezone(timezone.utc).isoformat(),
        "amber_at": amber_at.astimezone(timezone.utc).isoformat(),
        "elapsed_h": round(elapsed, 2),
        "remaining_h": round(remaining, 2)
    }

def set_status(cr: ChangeRequest, new_status: str, note: str = ""):
    """Single source of truth for status transitions: logs + history + SLA start."""
    from_status = cr.status or "NEW"
    cr.status = new_status
    cr.status_started_at = utcnow()
    db.session.add(CRStatusHistory(cr_id=cr.id, from_status=from_status, to_status=new_status, note=note))
    db.session.add(CRLog(cr_id=cr.id, stage="status", message=f"{from_status} → {new_status}", level="info"))
    db.session.commit()
