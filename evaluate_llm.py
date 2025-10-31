


import json
from app import app
from extensions import db
from models import ChangeRequest
from ai_llm import run_ai_for_cr

def main():
    with app.app_context():
        results = []
        for cr in db.session.query(ChangeRequest).order_by(ChangeRequest.id).all():
            data, _ = run_ai_for_cr(cr.id)
            results.append({
                "cr_id": cr.id,
                "title": cr.title,
                "predicted_department": data.get("predicted_department"),
                "confidence": data.get("confidence"),
                "matched_sops": data.get("matched_sops"),
                "owner": data.get("owner_name"),
            })
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
