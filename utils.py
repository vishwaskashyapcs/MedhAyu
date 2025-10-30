# utils.py
from extensions import db
from models import CRLog

def log_stage(cr_id, stage, message, level="info"):
    db.session.add(CRLog(cr_id=cr_id, stage=stage, message=message, level=level))
    db.session.commit()
