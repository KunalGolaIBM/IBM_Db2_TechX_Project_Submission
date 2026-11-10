import os, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

SAMPLE = [
 {"id":"s1","name":"Global STEM Futures Award","provider":"Example Education Foundation","country":"Global","study_levels":["Undergraduate","Masters"],"fields":["Computer Science","Engineering","Data Science"],"min_gpa":3.0,"funding":"Full tuition","deadline":"2027-03-15","description":"Illustrative award for technology and engineering students.","requirements":["Transcript","Personal statement","Reference letter"],"source_url":"https://example.org"},
 {"id":"s2","name":"East Africa Leadership Scholarship","provider":"Example Regional Scholars","country":"Rwanda","study_levels":["Undergraduate","Masters"],"fields":["Business","Public Policy","Computer Science"],"min_gpa":2.8,"funding":"Partial tuition + stipend","deadline":"2027-01-20","description":"Illustrative regional award for emerging leaders.","requirements":["Proof of residence","Transcript","Leadership essay"],"source_url":"https://example.org"},
 {"id":"s3","name":"Women in Data Scholarship","provider":"Example Data Initiative","country":"Global","study_levels":["Undergraduate","Masters","PhD"],"fields":["Data Science","Computer Science","Statistics"],"min_gpa":3.2,"funding":"Full tuition","deadline":"2027-05-01","description":"Illustrative funding for students studying data-related disciplines.","requirements":["Transcript","CV","Statement of purpose"],"source_url":"https://example.org"}
]

def get_items():
    dsn = os.getenv("DB2_DSN", "").strip()
    if not dsn: return SAMPLE, "sample-data"
    import ibm_db
    conn = ibm_db.connect(dsn, "", "")
    try:
        stmt = ibm_db.exec_immediate(conn, "SELECT ID, NAME, PROVIDER, COUNTRY, STUDY_LEVELS, FIELDS, MIN_GPA, FUNDING, DEADLINE, DESCRIPTION, REQUIREMENTS, SOURCE_URL FROM SCHOLARSHIPS")
        rows, row = [], ibm_db.fetch_assoc(stmt)
        while row:
            rows.append({"id":row["ID"],"name":row["NAME"],"provider":row["PROVIDER"],"country":row["COUNTRY"],"study_levels":json.loads(row["STUDY_LEVELS"]),"fields":json.loads(row["FIELDS"]),"min_gpa":float(row["MIN_GPA"]),"funding":row["FUNDING"],"deadline":row["DEADLINE"],"description":row["DESCRIPTION"],"requirements":json.loads(row["REQUIREMENTS"]),"source_url":row["SOURCE_URL"]})
            row = ibm_db.fetch_assoc(stmt)
        return rows, "ibm-db2"
    finally: ibm_db.close(conn)

app = FastAPI(title="ScholarFind AI API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("API_CORS_ORIGINS","http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])

class Profile(BaseModel):
    country: str = "Rwanda"
    study_level: str = "Undergraduate"
    field: str = "Computer Science"
    gpa: float = Field(3.2, ge=0, le=4)

@app.get("/api/health")
def health():
    return {"status":"ok","storage":"Db2 configured" if os.getenv("DB2_DSN","").strip() else "sample-data mode"}

@app.get("/api/scholarships")
def list_scholarships(q: str = ""):
    items, mode = get_items()
    if q: items = [x for x in items if q.lower() in (x["name"]+" "+x["description"]).lower()]
    return {"items":items,"count":len(items),"storage":mode}

@app.post("/api/match")
def match(profile: Profile):
    items, mode = get_items()
    ranked = []
    for x in items:
        checks = [(profile.study_level in x["study_levels"],35,"Study level"),(profile.field in x["fields"],35,"Field"),(profile.gpa >= x["min_gpa"],20,"GPA"),(x["country"].lower() in ("global",profile.country.lower()),10,"Country")]
        score, reasons = 0, []
        for ok, points, label in checks:
            if ok: score += points; reasons.append(label+" appears compatible")
            else: reasons.append("Check "+label.lower()+" requirements")
        ranked.append({**x,"match_score":score,"match_reasons":reasons})
    return {"items":sorted(ranked,key=lambda x:x["match_score"],reverse=True),"matching_method":"explainable-rules-v1","storage":mode}
