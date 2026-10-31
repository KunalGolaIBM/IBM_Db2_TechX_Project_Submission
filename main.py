from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from typing import Optional
from pathlib import Path
import tempfile, os

from analyzer import analyze, analyze_detailed
from auth import router as auth_router
from files import router as files_router
from links import router as links_router
from messenger_detector import router as message_router
from media_scam_detector import router as media_router
from scam_recovery_assistant import router as recovery_router

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="Digital Rakshak",
    description="Cyber safety and media scam analysis",
    version="3.0.0",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(files_router, prefix="/api", tags=["File Inspector"])
app.include_router(links_router, prefix="/api", tags=["Link Inspector"])
app.include_router(message_router, prefix="/api", tags=["Scam Message Detector"])
app.include_router(media_router, prefix="/api", tags=["Media Scam Detector"])
app.include_router(recovery_router, prefix="/api/recovery", tags=["Scam Recovery Assistant"])


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "application": "Digital Rakshak"}


async def _run(fn, text, file):
    path = None
    if file and file.filename:
        suffix = "_" + os.path.basename(file.filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            path = tmp.name
    try:
        return fn(text=text or None, path=path)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# ORIGINAL route, unchanged behavior
@app.post("/api/analyze", tags=["Combined Analyzer"])
async def analyze_all(text: Optional[str] = Form(None),
                      file: Optional[UploadFile] = File(None)):
    return await _run(analyze, text, file)


# NEW route with detailed checks, percentages and summary
@app.post("/api/analyze-detailed", tags=["Combined Analyzer"])
async def analyze_all_detailed(text: Optional[str] = Form(None),
                               file: Optional[UploadFile] = File(None)):
    return await _run(analyze_detailed, text, file)