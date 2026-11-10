import os
import shutil

SRC_ROOT = r"C:\Users\user\Documents\Lotline"
DEST_ROOT = r"C:\Users\user\Documents\IBM_Db2_TechX_Project_Submission\submissions\lotline"
DEST_SRC = os.path.join(DEST_ROOT, "src")

# 1. Clean destination src
if os.path.exists(DEST_SRC):
    shutil.rmtree(DEST_SRC)
os.makedirs(DEST_SRC, exist_ok=True)

# 2. Copy backend/app
backend_src = os.path.join(SRC_ROOT, "backend", "app")
backend_dest = os.path.join(DEST_SRC, "backend", "app")
shutil.copytree(backend_src, backend_dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env*"))
print(f"Copied backend/app to {backend_dest}")

# 3. Copy backend/tests
tests_src = os.path.join(SRC_ROOT, "backend", "tests")
tests_dest = os.path.join(DEST_SRC, "backend", "tests")
shutil.copytree(tests_src, tests_dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache*"))
print(f"Copied backend/tests to {tests_dest}")

# 4. Copy backend/scripts
scripts_src = os.path.join(SRC_ROOT, "backend", "scripts")
scripts_dest = os.path.join(DEST_SRC, "backend", "scripts")
shutil.copytree(scripts_src, scripts_dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "raw_video*", "*.webm", "*.mp4"))
print(f"Copied backend/scripts to {scripts_dest}")

# 5. Copy frontend (selective)
frontend_dest = os.path.join(DEST_SRC, "frontend")
os.makedirs(frontend_dest, exist_ok=True)

frontend_dirs = ["src", "public"]
for d in frontend_dirs:
    s = os.path.join(SRC_ROOT, "frontend", d)
    t = os.path.join(frontend_dest, d)
    if os.path.exists(s):
        shutil.copytree(s, t, ignore=shutil.ignore_patterns("node_modules", "dist", ".cache"))
        print(f"Copied frontend/{d} to {t}")

frontend_files = [
    "index.html",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.ts",
    "tailwind.config.js",
    "postcss.config.js"
]
for f in frontend_files:
    s = os.path.join(SRC_ROOT, "frontend", f)
    t = os.path.join(frontend_dest, f)
    if os.path.exists(s):
        shutil.copy2(s, t)
        print(f"Copied frontend/{f}")

# 6. Generate requirements.txt in submissions/lotline/requirements.txt and src/
reqs = """# LOTLINE Python Backend Dependencies
# IBM Db2 TechX Summit 2026 Submission
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
ibm_db>=3.2.0
langgraph>=0.2.20
langchain>=0.3.0
langchain-core>=0.3.0
google-genai>=0.1.0
pydantic>=2.8.0
python-dotenv>=1.0.0
reportlab>=4.2.0
requests>=2.31.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
pymupdf>=1.24.0
playwright>=1.45.0
"""
with open(os.path.join(DEST_ROOT, "requirements.txt"), "w", encoding="utf-8") as f:
    f.write(reqs)
with open(os.path.join(DEST_SRC, "requirements.txt"), "w", encoding="utf-8") as f:
    f.write(reqs)
print("Created requirements.txt")

print("\nSource packaging completed successfully!")
