from fastapi import APIRouter, UploadFile, File, HTTPException
from common import MAX_FILE_SIZE, sha256_bytes, make_report

router = APIRouter()

DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".scr", ".bat", ".cmd", ".com", ".ps1", ".vbs", ".js",
    ".jar", ".msi", ".hta", ".apk", ".iso", ".lnk"
}
SUSPICIOUS_BYTES = [
    (b"powershell -enc", "Contains a PowerShell encoded-command indicator."),
    (b"cmd.exe", "Contains a Windows command-shell indicator."),
    (b"CreateRemoteThread", "Contains a process-injection API string."),
    (b"VirtualAlloc", "Contains a memory-allocation API string sometimes seen in malware."),
    (b"AutoOpen", "Contains a macro auto-run keyword."),
    (b"Shell(", "Contains a script-shell keyword."),
]

@router.post("/scan")
async def scan_file(file: UploadFile = File(...)):
    data = await file.read(MAX_FILE_SIZE + 1)
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds the 10 MB limit.")
    name = (file.filename or "upload.bin")
    lower = name.lower()
    score, findings = 0, []
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext in DANGEROUS_EXTENSIONS:
        score += 55
        findings.append(f"Potentially executable or script-based file type: {ext}")
    parts = lower.split(".")
    if len(parts) >= 3 and parts[-2] in {"pdf", "doc", "docx", "jpg", "png", "txt"} and parts[-1] in {"exe", "scr", "js", "bat", "cmd", "vbs"}:
        score += 35
        findings.append("Double-extension pattern may disguise the actual file type.")
    signatures = {
        b"MZ": "Windows PE executable signature detected.",
        b"%PDF": "PDF file signature detected.",
        b"PK\x03\x04": "ZIP-based container signature detected (for example DOCX/XLSX/ZIP).",
        b"\x7fELF": "ELF executable signature detected.",
        b"\xd0\xcf\x11\xe0": "OLE compound document signature detected; legacy Office documents may contain macros."
    }
    for sig, text in signatures.items():
        if data.startswith(sig):
            findings.append(text)
            if sig in (b"MZ", b"\x7fELF"):
                score += 30
            break
    for pattern, text in SUSPICIOUS_BYTES:
        if pattern.lower() in data.lower():
            score += 12
            findings.append(text)
    if b"vbaProject.bin" in data or b"VBA" in data[:200000]:
        score += 20
        findings.append("Possible VBA/macro-related content marker detected.")
    if not findings:
        findings.append("No known filename, signature, or byte-pattern warning was triggered.")
    digest = sha256_bytes(data)
    report = make_report("File Inspector", min(score, 100), findings)
    report.update({"filename": name, "size_bytes": len(data), "sha256": digest})
    return report
