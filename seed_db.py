

# seed_db.py
import pandas as pd
from datetime import datetime, timezone

from app import app
from extensions import db
from models import Department, User, SOPItem, ChangeRequest, SLA

def run():
    with app.app_context():
        # fresh schema for the demo
        db.drop_all()
        db.create_all()

        # ---- seed Departments
        depts = pd.read_csv("data/departments.csv", dtype={"department_id": int, "name": str})
        for _, r in depts.iterrows():
            db.session.add(Department(id=int(r["department_id"]), name=str(r["name"])))

        # ---- seed Users
        users = pd.read_csv("data/users.csv", dtype=str)
        for _, r in users.iterrows():
            db.session.add(User(
                id=int(r["user_id"]),
                name=str(r["name"]),
                email=str(r["email"]),
                role=str(r["role"]),
                department_id=int(r["department_id"])
            ))

        # ---- seed SOPs
        sops = pd.read_csv("data/sop_items.csv", dtype=str)
        for _, r in sops.iterrows():
            db.session.add(SOPItem(
                code=str(r["code"]),
                title=str(r["title"]),
                content_snippet=str(r["content_snippet"]),
                keywords=str(r["keywords"]),
                owner_department=str(r["owner_department"])
            ))

        # ---- seed Change Requests
        # now = datetime.now(timezone.utc)
        # crs = pd.read_csv("data/cr_samples.csv", dtype=str)
        # for _, r in crs.iterrows():
        #     db.session.add(ChangeRequest(
        #         id=int(r["cr_id"]),
        #         title=str(r["title"]),
        #         department=str(r["department"]),
        #         risk=str(r["risk"]),
        #         description=str(r["description"]),
        #         status="NEW",
        #         status_started_at=now   # start SLA clock for seeded CRs
        #     ))
        # seed_db.py (snippet in the "seed Change Requests" loop)

# ---- seed Change Requests
        now = datetime.now(timezone.utc)
        crs = pd.read_csv("data/cr_samples.csv", dtype=str)
        for _, r in crs.iterrows():
            baseline_str = r.get("manual_baseline_hours")
            try:
                baseline = float(baseline_str) if baseline_str not in (None, "", "nan") else None
            except Exception:
                baseline = 24.0
            db.session.add(ChangeRequest(
                id=int(r["cr_id"]),
                title=str(r["title"]),
                department=str(r["department"]),
                risk=str(r["risk"]),
                description=str(r["description"]),
                status="NEW",
                status_started_at=now,
                manual_baseline_hours=baseline
            ))


        # ---- seed SLA policies
        sla = pd.read_csv(
            "data/sla_policies.csv",
            dtype={"status": str, "sla_hours": int, "amber_threshold_hours": int}
        )
        for _, r in sla.iterrows():
            db.session.add(SLA(
                status=r["status"],
                sla_hours=int(r["sla_hours"]),
                amber_threshold_hours=int(r["amber_threshold_hours"])
            ))

        db.session.commit()
        print("✅ Seed complete.")

if __name__ == "__main__":
    run()
