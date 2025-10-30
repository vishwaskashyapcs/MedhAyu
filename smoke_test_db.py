# smoke_test_db.py
from app import app, db
from models import Department, User, SOPItem, ChangeRequest, SLA

def show_counts():
    print("Departments:", Department.query.count())
    print("Users:", User.query.count())
    print("SOPItems:", SOPItem.query.count())
    print("ChangeRequests:", ChangeRequest.query.count())
    print("SLA rows:", SLA.query.count())

def sample_queries():
    print("\nOne QA user:")
    qa_user = User.query.join(Department, User.department_id == Department.id).filter(Department.name=="Quality Assurance").first()
    if qa_user:
        print(f"- {qa_user.name} ({qa_user.email}) in QA")

    print("\nCRs tagged 'Moderate' risk:")
    for cr in ChangeRequest.query.filter_by(risk="Moderate").limit(3).all():
        print(f"- #{cr.id}: {cr.title} [{cr.department}]")

    print("\nSOPs owned by 'Engineering':")
    for sop in SOPItem.query.filter_by(owner_department="Engineering").all():
        print(f"- {sop.code}: {sop.title}")

if __name__ == "__main__":
    with app.app_context():
        show_counts()
        sample_queries()
