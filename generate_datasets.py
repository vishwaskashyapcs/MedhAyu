import pandas as pd, random
from datetime import datetime
from pathlib import Path

base = Path("data")
base.mkdir(exist_ok=True)

departments = [
    (1, "Manufacturing"),
    (2, "Quality Assurance"),
    (3, "Quality Control"),
    (4, "Engineering"),
    (5, "Validation / CSV"),
    (6, "IT Systems"),
    (7, "Regulatory Affairs"),
    (8, "Supply Chain / Warehouse"),
    (9, "EHS"),
    (10, "R&D / Formulation"),
]
pd.DataFrame(departments, columns=["department_id","name"]).to_csv(base/"departments.csv", index=False)

users = [
    (1,"Asha Menon","asha.menon@plant.local","user",1),
    (2,"Ravi Kumar","ravi.kumar@plant.local","dept_head",1),
    (3,"Priya Nair","priya.nair@qa.local","qa",2),
    (4,"Anil Verma","anil.verma@qc.local","dept_head",3),
    (5,"Deepa Iyer","deepa.iyer@eng.local","dept_head",4),
    (6,"Neha Gupta","neha.gupta@validation.local","dept_head",5),
    (7,"Vikas Shah","vikas.shah@it.local","dept_head",6),
    (8,"Sonia Rao","sonia.rao@regaff.local","dept_head",7),
    (9,"Mohit Jain","mohit.jain@supply.local","dept_head",8),
    (10,"Kiran Patil","kiran.patil@ehs.local","dept_head",9),
    (11,"Nisha Kulkarni","nisha.kulkarni@rnd.local","dept_head",10),
]
pd.DataFrame(users, columns=["user_id","name","email","role","department_id"]).to_csv(base/"users.csv", index=False)

sops = [
    ("SOP-MFG-03","Line 3 Nozzle Replacement","Procedure for nozzle replacement and verification","Manufacturing","line 3,nozzle,replacement,CAPA"),
    ("SOP-QA-08","SOP Revision and Version Control","Controlled SOP revision and review cycles","Quality Assurance","SOP,revision,document control,training"),
    ("SOP-QC-05","HPLC Method Validation","HPLC method validation and acceptance criteria","Quality Control","HPLC,assay,validation,column"),
    ("SOP-ENG-10","Preventive Maintenance","Define PM frequency and critical equipment","Engineering","maintenance,PM,calibration,equipment"),
    ("SOP-CSV-07","CSV for ETL Pipelines","Validation of CSV ingestion and hashing","Validation / CSV","CSV,ETL,ingestion,checksum,pipeline"),
    ("SOP-IT-SEC-02","Access Control & Backups","IT access and backup procedures","IT Systems","LIMS,MES,backup,restore,access"),
    ("SOP-RA-04","Labeling & Dossier Alignment","Changes to labeling content","Regulatory Affairs","label,packaging,dossier,submission"),
    ("SOP-SC-06","Approved Supplier Change","Supplier change and material qualification","Supply Chain / Warehouse","supplier,vendor,material,COA"),
    ("SOP-EHS-03","PPE & Waste Segregation","Safety PPE and waste segregation","EHS","PPE,spill,hazard,segregation,waste"),
    ("SOP-RND-12","Scale-Up Parameter Transfer","Transfer of process parameters","R&D / Formulation","scale-up,formulation,mixing,granulation"),
]
pd.DataFrame(sops, columns=["code","title","content_snippet","owner_department","keywords"]).to_csv(base/"sop_items.csv", index=False)

cr_samples = [
    (1,"Replace nozzle on Line 3 due to corrosion","Manufacturing","Moderate",
     "Current SS nozzle shows corrosion; propose coated titanium; affects batch record."),
    (2,"Revise SOP for electronic signatures","Quality Assurance","Minor",
     "Update Part 11 section; training and audit impact."),
    (3,"Adopt new HPLC column for assay method","Quality Control","Moderate",
     "Column backpressure issues; new column validation."),
    (4,"Change PM frequency for autoclave","Engineering","Minor",
     "PM from 6 to 3 months; calibration record update."),
    (5,"Upgrade CSV ingestion ETL","Validation / CSV","Moderate",
     "Fix checksum errors; improve audit trail."),
    (6,"Update backup policy for MES","IT Systems","Minor",
     "Add weekly restore test; improve access control."),
    (7,"Update carton label warning","Regulatory Affairs","Moderate",
     "Add black box warning per guidance."),
    (8,"Change API supplier","Supply Chain / Warehouse","Major",
     "Vendor A to Vendor B; requalification needed."),
    (9,"Revise PPE requirement for solvents","EHS","Minor",
     "Add face shield; training impact."),
    (10,"Adjust granulation mixing time","R&D / Formulation","Moderate",
     "Mixing 8→10 min; process validation impact.")
]
pd.DataFrame(cr_samples, columns=["cr_id","title","department","risk","description"]).to_csv(base/"cr_samples.csv", index=False)

sla = [
    ("NEW",48,42),
    ("IN_REVIEW",72,60),
    ("QA_REVIEW",48,42),
    ("IMPLEMENTED",0,0),
    ("CLOSED",0,0)
]
pd.DataFrame(sla, columns=["status","sla_hours","amber_threshold_hours"]).to_csv(base/"sla_policies.csv", index=False)

print("✅ All CSVs created in ./data/")
