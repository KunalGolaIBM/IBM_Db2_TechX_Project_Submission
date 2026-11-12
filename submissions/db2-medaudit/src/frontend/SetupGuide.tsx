import React, { useState } from 'react';
import { Terminal, Copy, Check, FileCode2, Package, Layers, Sparkles, BookOpen, AlertCircle, Download } from 'lucide-react';

export const SetupGuide: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyCode = (id: string, code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const pythonPackagesCode = `# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\\Scripts\\activate

# 2. Install IBM DB2 Driver & SQLAlchemy Adapter
# Note: ibm-db automatically fetches the native IBM CLI driver (clidriver)
pip install ibm-db ibm-db-sa sqlalchemy

# 3. Install AI Framework (LangChain or CrewAI)
pip install langchain langchain-community langchain-core langchain-google-genai

# 4. (Optional for CrewAI multi-agent setup)
pip install crewai crewai-tools`;

  const clidriverConfigCode = `# Linux / Docker:
export IBM_DB_HOME=/usr/local/lib/python3.11/site-packages/clidriver
export LD_LIBRARY_PATH=$IBM_DB_HOME/lib:$LD_LIBRARY_PATH

# macOS (Darwin):
export IBM_DB_HOME=$(python -c "import site; print(site.getsitepackages()[0])")/clidriver
export DYLD_LIBRARY_PATH=$IBM_DB_HOME/lib:$DYLD_LIBRARY_PATH

# Windows PowerShell:
$env:IBM_DB_HOME = "C:\\Python311\\Lib\\site-packages\\clidriver"
$env:PATH += ";$env:IBM_DB_HOME\\bin"`;

  const dockerDb2Code = `# Pull and run official IBM DB2 Community Edition container
docker run -itd --name db2server \\
  --restart=always \\
  -e LICENSE=accept \\
  -e DB2INST1_PASSWORD=db2password123 \\
  -e DBNAME=MEDAUDIT \\
  -e BLU=false \\
  -e ENABLE_ORACLE_COMPATIBILITY=false \\
  -p 50000:50000 \\
  -p 50001:50001 \\
  --privileged=true \\
  ibmcom/db2:11.5.8.0

# Verify container logs
docker logs -f db2server`;

  const langchainPythonCode = `import os
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# 1. Configure DB2 Connection URI
# Format: db2+ibm_db://<username>:<password>@<host>:<port>/<database>
DB2_USER = os.getenv("DB2_USER", "db2inst1")
DB2_PASS = os.getenv("DB2_PASS", "db2password123")
DB2_HOST = os.getenv("DB2_HOST", "localhost")
DB2_PORT = os.getenv("DB2_PORT", "50000")
DB2_DB   = os.getenv("DB2_DB", "MEDAUDIT")

db_uri = f"db2+ibm_db://{DB2_USER}:{DB2_PASS}@{DB2_HOST}:{DB2_PORT}/{DB2_DB}"
db = SQLDatabase.from_uri(db_uri, include_tables=[
    "CLINICAL_GUIDELINES",
    "LAB_COMMISSION_CONTRACTS",
    "DOCTORS",
    "TEST_CATALOG"
])

# 2. Initialize Gemini 3.8 Flash model
llm = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.0
)

# 3. Create LangChain SQL Agent with Medical Audit Instruction
system_prompt = """
You are a Medical Prescription Auditor. Your goal is to detect unnecessary medical tests
and flag doctor-lab kickback contracts by querying the IBM DB2 database.
Query CLINICAL_GUIDELINES for indicated/contraindicated tests.
Query LAB_COMMISSION_CONTRACTS to check if the doctor receives kickbacks for the ordered tests.
Always explain the clinical necessity tier: Essential, Conditional, or Unwarranted.
"""

agent_executor = create_sql_agent(
    llm=llm,
    db=db,
    agent_type="openai-tools",
    verbose=True
)

# 4. Audit query
patient_query = """
Patient is a 29-year-old female with acute sore throat and runny nose for 3 days.
Dr. Rajesh Sharma ordered: Brain CT Scan ($280) and Full Allergy IgE Panel ($260) at MetroScan Diagnostics.
Audit these test orders against DB2 guidelines and check for referral kickbacks.
"""

response = agent_executor.invoke({"input": patient_query})
print(response["output"])`;

  const crewAiCode = `from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool

# Agent 1: Clinical Necessity Specialist
guidelines_agent = Agent(
    role="Clinical Practice Guideline Specialist",
    goal="Verify if prescribed diagnostic tests are indicated by evidence-based medicine",
    backstory="Board-certified internal medicine reviewer knowledgeable in NICE, WHO, and ICMR protocols.",
    verbose=True
)

# Agent 2: Forensic Financial Kickback Investigator
fraud_agent = Agent(
    role="Medical Billing & Lab Kickback Auditor",
    goal="Detect hidden referral fee agreements between doctors and private diagnostic labs in IBM DB2",
    backstory="Former healthcare compliance officer specialized in uncovering commercial referral kickbacks.",
    verbose=True
)

# Tasks & Crew Assembly
audit_task = Task(
    description="Cross-reference Dr. Sharma's order (Brain CT for sore throat) against DB2 clinical tables.",
    expected_output="Itemized breakdown of test validity and estimated financial overcharge.",
    agent=guidelines_agent
)

crew = Crew(
    agents=[guidelines_agent, fraud_agent],
    tasks=[audit_task],
    process=Process.sequential
)

result = crew.kickoff()
print(result)`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-sky-700 uppercase tracking-wider mb-1">
              <span>Developer Execution Blueprint</span>
              <span aria-hidden="true">·</span>
              <span>IBM DB2 & AI Framework Integration</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              Package Setup & LangChain Implementation Plan
            </h1>
            <p className="mt-1 text-sm text-slate-600 max-w-3xl">
              Complete guide on handling package downloads, configuring native IBM CLI drivers (`clidriver`), running local DB2 containers, and connecting with LangChain or CrewAI.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <a
              href="/db2-medaudit-solution.zip"
              download="db2-medaudit-solution.zip"
              className="p-3 bg-sky-700 hover:bg-sky-800 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-xs"
            >
              <Download className="w-4 h-4" />
              <span>Download Project ZIP (70 KB)</span>
            </a>

            <div className="p-3 bg-sky-50 border border-sky-100 rounded-lg text-xs flex items-center gap-3">
              <Package className="w-5 h-5 text-sky-700 shrink-0" />
              <div>
                <span className="font-bold text-sky-900 block">Supported Frameworks</span>
                <span className="text-slate-600">LangChain · CrewAI · Haystack</span>
              </div>
            </div>
          </div>
        </div>

        {/* 4-Step Architecture Steps */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="font-bold text-slate-900 block mb-1">Step 1: Python / Node</span>
            <span className="text-slate-600">Install `ibm-db` & AI framework packages.</span>
          </div>
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="font-bold text-slate-900 block mb-1">Step 2: CLI Driver</span>
            <span className="text-slate-600">Configure `IBM_DB_HOME` & library path.</span>
          </div>
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="font-bold text-slate-900 block mb-1">Step 3: DB2 Container</span>
            <span className="text-slate-600">Run IBM DB2 LUW or connect to Cloud.</span>
          </div>
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="font-bold text-slate-900 block mb-1">Step 4: AI Agent</span>
            <span className="text-slate-600">Execute clinical audit with Gemini.</span>
          </div>
        </div>
      </div>

      {/* Code Section 1: Package Downloads & CLI Driver */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        
        {/* Step 1 Code */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-sky-600" />
                1. Package Downloads (pip / virtualenv)
              </h2>
              <span className="text-xs text-slate-500">Essential Python libraries for DB2 & LangChain</span>
            </div>
            <button
              onClick={() => copyCode('step1', pythonPackagesCode)}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs flex items-center gap-1"
            >
              {copiedId === 'step1' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedId === 'step1' ? 'Copied' : 'Copy'}
            </button>
          </div>

          <pre className="p-3.5 bg-slate-950 text-sky-200 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{pythonPackagesCode}</code>
          </pre>

          <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong className="font-bold">Note on `ibm-db` download:</strong> During `pip install ibm-db`, the wheel automatically downloads the compiled IBM CLI driver tarball (~35MB) for your operating system (Linux x86_64, macOS, or Windows).
            </div>
          </div>
        </div>

        {/* Step 2 Code: CLI Driver Config */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Layers className="w-4 h-4 text-sky-600" />
                2. Native CLI Driver (`clidriver`) Path Setup
              </h2>
              <span className="text-xs text-slate-500">Preventing `libdb2.so` dynamic library link errors</span>
            </div>
            <button
              onClick={() => copyCode('step2', clidriverConfigCode)}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs flex items-center gap-1"
            >
              {copiedId === 'step2' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedId === 'step2' ? 'Copied' : 'Copy'}
            </button>
          </div>

          <pre className="p-3.5 bg-slate-950 text-emerald-200 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{clidriverConfigCode}</code>
          </pre>

          <p className="text-xs text-slate-600 leading-relaxed">
            If your application fails with <code>ImportError: libdb2.so.1: cannot open shared object file</code>, setting the <code>LD_LIBRARY_PATH</code> variable as shown above directs the dynamic linker to the embedded IBM DB2 client binaries.
          </p>
        </div>

      </div>

      {/* Code Section 2: Docker Setup & LangChain Code */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left: Docker DB2 LUW (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileCode2 className="w-4 h-4 text-sky-600" />
                3. Local IBM DB2 Container (Docker)
              </h2>
              <span className="text-xs text-slate-500">Official IBM DB2 Community Edition</span>
            </div>
            <button
              onClick={() => copyCode('docker', dockerDb2Code)}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs flex items-center gap-1"
            >
              {copiedId === 'docker' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedId === 'docker' ? 'Copied' : 'Copy'}
            </button>
          </div>

          <pre className="p-3.5 bg-slate-950 text-slate-200 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{dockerDb2Code}</code>
          </pre>

          <div className="text-xs text-slate-600 space-y-2">
            <span className="font-bold text-slate-800 block">DB2 Container Parameters:</span>
            <ul className="list-disc pl-4 space-y-1">
              <li><strong>Port 50000</strong>: Standard DB2 connection port</li>
              <li><strong>Port 50001</strong>: SSL encrypted communications port</li>
              <li><strong>Database Name</strong>: <code>MEDAUDIT</code></li>
              <li><strong>Default Admin User</strong>: <code>db2inst1</code></li>
            </ul>
          </div>
        </div>

        {/* Right: LangChain Python Script (7 cols) */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sky-600" />
                4. LangChain SQL Agent with IBM DB2 & Gemini
              </h2>
              <span className="text-xs text-slate-500">Production agent script querying clinical guidelines</span>
            </div>
            <button
              onClick={() => copyCode('langchain', langchainPythonCode)}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs flex items-center gap-1"
            >
              {copiedId === 'langchain' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedId === 'langchain' ? 'Copied' : 'Copy'}
            </button>
          </div>

          <pre className="p-3.5 bg-slate-950 text-sky-200 rounded-lg text-xs font-mono overflow-x-auto max-h-96 leading-relaxed">
            <code>{langchainPythonCode}</code>
          </pre>
        </div>

      </div>

      {/* Alternative AI Framework: CrewAI Multi-Agent */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-purple-600" />
              Alternative AI Framework: CrewAI Multi-Agent Architecture
            </h2>
            <span className="text-xs text-slate-500">Separating Clinical Necessity from Forensic Financial Audit</span>
          </div>
          <button
            onClick={() => copyCode('crewai', crewAiCode)}
            className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs flex items-center gap-1"
          >
            {copiedId === 'crewai' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            {copiedId === 'crewai' ? 'Copied' : 'Copy'}
          </button>
        </div>

        <pre className="p-3.5 bg-slate-950 text-purple-200 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed">
          <code>{crewAiCode}</code>
        </pre>
      </div>

    </div>
  );
};
