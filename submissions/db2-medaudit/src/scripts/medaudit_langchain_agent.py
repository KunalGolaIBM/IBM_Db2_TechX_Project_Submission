"""
DB2 MedAudit - LangChain SQL Clinical Agent
Connects to IBM DB2 and verifies medical test prescriptions against clinical guidelines.
"""
import os
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

def build_medaudit_agent():
    # 1. DB2 Connection URI (db2+ibm_db://<user>:<password>@<host>:<port>/<dbname>)
    db2_user = os.getenv("DB2_USER", "db2inst1")
    db2_pass = os.getenv("DB2_PASS", "db2password123")
    db2_host = os.getenv("DB2_HOST", "localhost")
    db2_port = os.getenv("DB2_PORT", "50000")
    db2_name = os.getenv("DB2_DB", "MEDAUDIT")

    db_uri = f"db2+ibm_db://{db2_user}:{db2_pass}@{db2_host}:{db2_port}/{db2_name}"
    
    print(f"Connecting to IBM DB2 at {db2_host}:{db2_port}/{db2_name}...")
    db = SQLDatabase.from_uri(db_uri, include_tables=[
        "CLINICAL_GUIDELINES",
        "LAB_COMMISSION_CONTRACTS",
        "DOCTORS",
        "TEST_CATALOG"
    ])

    # 2. LLM Engine using Gemini 3.8 Flash
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.0
    )

    # 3. Create SQL Agent
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="openai-tools",
        verbose=True
    )
    return agent_executor

if __name__ == "__main__":
    agent = build_medaudit_agent()
    
    sample_audit = """
    Patient: 29yo female.
    Chief Complaint: Acute mild sore throat and clear rhinorrhea for 3 days. Normal vitals.
    Doctor: Dr. Rajesh Sharma at Apex Care Polyclinic.
    Recommended Lab: MetroScan Premium Diagnostics.
    Ordered Tests:
    1. Rapid Strep Antigen Test ($30)
    2. Brain CT Scan with contrast ($280)
    3. Full 32-Allergen Blood IgE Panel ($260)
    
    Audit this order against CLINICAL_GUIDELINES and check LAB_COMMISSION_CONTRACTS for referral kickback ties.
    Itemize each test necessity (Essential, Conditional, Unwarranted) and calculate patient savings.
    """
    
    print("Executing Clinical Audit Query...")
    result = agent.invoke({"input": sample_audit})
    print("\n--- CLINICAL AUDIT REPORT ---")
    print(result["output"])
