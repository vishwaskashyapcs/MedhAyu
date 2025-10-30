# models.py
from extensions import db  # <-- instead of from app import db

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    users = db.relationship("User", backref="department_obj", lazy=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    role = db.Column(db.String(30))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))

class SOPItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    title = db.Column(db.String(200))
    content_snippet = db.Column(db.Text)
    keywords = db.Column(db.Text)
    owner_department = db.Column(db.String(100))

class ChangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    department = db.Column(db.String(100))
    risk = db.Column(db.String(50))
    description = db.Column(db.Text)
    status = db.Column(db.String(30), default="NEW")
    ai_summary = db.Column(db.JSON, nullable=True)
    ai_routing = db.Column(db.JSON, nullable=True)

    # models.py (only the DateTime fields shown)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=db.func.now())
    status_started_at = db.Column(db.DateTime(timezone=True), nullable=True)

    manual_baseline_hours = db.Column(db.Float)  # “typical” manual TAT for this CR
    ai_elapsed_seconds = db.Column(db.Integer, nullable=True)

class SLA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(30), unique=True)
    sla_hours = db.Column(db.Integer)
    amber_threshold_hours = db.Column(db.Integer)

class CRLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cr_id = db.Column(db.Integer, db.ForeignKey('change_request.id'), index=True, nullable=False)
    stage = db.Column(db.String(50))      # e.g., "summarize", "match_sops", "route", "decision"
    message = db.Column(db.Text)
    level = db.Column(db.String(10), default="info")  # info|warn|error
    ts = db.Column(db.DateTime, server_default=db.func.now())

class CRStatusHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cr_id = db.Column(db.Integer, db.ForeignKey('change_request.id'), index=True, nullable=False)
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30))
    changed_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    note = db.Column(db.Text)