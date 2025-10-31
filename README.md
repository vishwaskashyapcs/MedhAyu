# 🧠 MedhAyu – Intelligent Change Control Assistant

> A smart AI-driven system to automate pharmaceutical Change Control processes, reduce manual turnaround time (TAT), and ensure compliance using intelligent routing, SLA tracking, and real-time reporting.

---

## 🏭 Project Overview

Traditional **Change Control** processes in pharma manufacturing are **manual, time-consuming, and prone to delays**.  
Every change request (CR) — such as an equipment replacement, SOP revision, or material update — must pass through multiple departments (Manufacturing, QA, QC, Engineering, etc.) before closure.

**MedhAyu** automates this process using **AI-assisted classification**, **speech-to-text input**, and **real-time SLA monitoring**.

---

### 🧩 Problem Statement

- Manual routing of Change Requests causes **delays (24–72 hrs)** in approval cycles.
- Department selection and SOP matching depend on human expertise.
- Lack of real-time visibility into SLA breaches or departmental bottlenecks.
- No unified dashboard or reporting for QA oversight.

---

### 💡 Proposed Solution

- Use **LLM (OpenAI GPT)** to automatically:
  - Summarize CRs into *Problem / Justification / Impact*.
  - Predict the correct **Department** & **Owner**.
  - Match relevant **SOPs**.
- Integrate **Speech-to-Text (STT)** for voice-based CR entry.
- Provide **SLA-based turnaround tracking** and AI vs manual time savings.
- Enable **QA Super Admin** to generate instant PDF reports:
  - Total CRs, Closed CRs, Estimated time.
  - Department-wise breakdown.
  - SLA compliance and AI time saved.

---

## ⚙️ System Architecture

📂 MedhAyu/
│
├── app.py # Flask app entry point
├── extensions.py # SQLAlchemy setup
│
├── models.py # ORM models: CR, User, Department, SOP, SLA
├── seed_db.py # Loads demo data (departments, users, SOPs, SLA)
│
├── routes_ui.py # Tailwind UI for Users, Dept Admins, QA
├── routes_core.py # API routes: CR flow, approvals, SLA, QA reports
├── routes_ai.py # AI endpoints to trigger GPT-based analysis
├── ai_llm.py # OpenAI LLM integration (CR summarization + routing)
│
├── utils.py # Logging helper
├── utils_sla.py # SLA computation and status handling
├── utils_benchmark.py # Manual TAT estimation for comparison
│
├── data/ # CSVs for departments, users, SOPs, SLAs, CR samples
└── static/ or templates/ # (auto-rendered by routes_ui)


## ⚡ Setup & Run Instructions

### 1️⃣ Clone Repository

```bash
git clone https://github.com/yourusername/MedhAyu.git
cd MedhAyu


2️⃣ Create Virtual Environment
python -m venv medhayu-env
medhayu-env\Scripts\activate      # Windows
# or
source medhayu-env/bin/activate   # Linux/Mac

3️⃣ Install Requirements
pip install -r requirements.txt

4️⃣ Create .env File
OPENAI_API_KEY=sk-xxxxxx
OPENAI_MODEL=gpt-4o-mini
CONFIDENCE_THRESHOLD=0.6
DATABASE_URL=sqlite:///change_control.db

5️⃣ Seed Database
python seed_db.py


✅ You should see:

✅ Seed complete.

6️⃣ Run the App
flask run
# or
python app.py


🌐 Visit: http://127.0.0.1:5000/