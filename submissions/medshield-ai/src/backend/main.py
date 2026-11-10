from fastapi import FastAPI, HTTPException
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List
from .db import init_db, execute, rows
from .agent import analyze

app=FastAPI(title="MEDSHIELD AI", version="1.0.0", description="Medication safety decision-support prototype")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class AnalysisRequest(BaseModel):
    patient_id: str = "DEMO-001"
    medications: List[str] = Field(min_length=1, description="Medication names")
    allergies: List[str] = []

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    try:
        rows("SELECT PATIENT_ID FROM PATIENTS")
        return {"status":"ok","database":"connected","mode":"IBM Db2" if __import__('os').getenv('DB2_DSN') else "SQLite demo fallback"}
    except Exception as e: raise HTTPException(503,str(e))

@app.get("/api/demo-patient")
def demo_patient():
    return {"patient_id":"DEMO-001","patient_name":"Alex Demo","age":45,"note":"Fictional demonstration record"}

@app.post("/api/analyze")
def analyze_route(req: AnalysisRequest):
    try:
        result=analyze(req.medications,req.allergies)
        findings=result.get('findings',[])
        # Store a durable report in the configured database.
        report_id=time.time_ns() % 2000000000
        execute("INSERT INTO SAFETY_REPORTS (REPORT_ID, PATIENT_ID, RISK_LEVEL, FINDINGS) VALUES (?, ?, ?, ?)",
                (report_id,req.patient_id,result['risk'],str(findings)))
        return {"patient_id":req.patient_id,"risk":result['risk'],"summary":result['summary'],"findings":findings,
                "medications":req.medications,"disclaimer":"Prototype screening only. Not a diagnosis or prescribing recommendation. A qualified clinician/pharmacist must review all results."}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/reports")
def reports():
    try: return rows("SELECT REPORT_ID, PATIENT_ID, RISK_LEVEL, FINDINGS, CREATED_AT FROM SAFETY_REPORTS ORDER BY CREATED_AT DESC")
    except Exception as e: raise HTTPException(500,str(e))

app.mount("/",StaticFiles(directory="src/frontend",html=True),name="frontend")
