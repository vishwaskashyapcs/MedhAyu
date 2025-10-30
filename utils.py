

    
# utils.py
from datetime import datetime
from extensions import db
from models import CRLog

def log_stage(cr_id: int, stage: str, message: str, level: str = "info"):
    try:
        db.session.add(CRLog(cr_id=cr_id, stage=stage, message=message, level=level, ts=datetime.utcnow()))
        db.session.commit()
    except Exception:
        db.session.rollback()

