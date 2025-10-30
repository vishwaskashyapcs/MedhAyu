import pandas as pd
from app import app, db
from models import Department, User, SOPItem, ChangeRequest, SLA

def run():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Departments
        for _, r in pd.read_csv("data/departments.csv").iterrows():
            db.session.add(Department(id=int(r.department_id), name=r.name))

        # Users
        for _, r in pd.read_csv("data/users.csv").iterrows():
            db.session.add(User(
                id=int(r.user_id), name=r.name, email=r.email,
                role=r.role, department_id=int(r.department_id)
            ))

        # SOPs
        for _, r in pd.read_csv("data/sop_items.csv").iterrows():
            db.session.add(SOPItem(
                code=r.code, title=r.title, content_snippet=r.content_snippet,
                keywords=r.keywords, owner_department=r.owner_department
            ))

        # CRs
        for _, r in pd.read_csv("data/cr_samples.csv").iterrows():
            db.session.add(ChangeRequest(
                id=int(r.cr_id), title=r.title, department=r.department,
                risk=r.risk, description=r.description
            ))

        # SLA
        for _, r in pd.read_csv("data/sla_policies.csv").iterrows():
            db.session.add(SLA(status=r.status,
                               sla_hours=int(r.sla_hours),
                               amber_threshold_hours=int(r.amber_threshold_hours)))

        db.session.commit()
        print("✅ Seed complete.")

if __name__ == "__main__":
    run()
