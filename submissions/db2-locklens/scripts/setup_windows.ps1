# Creates .env.db2 (for the Db2 container) and .env (for LockLens) with ONE shared password,
# so the two files cannot get out of sync. Run from the submissions\db2-locklens folder:
#     powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
# Both files are git-ignored. Nothing is sent anywhere.
$ErrorActionPreference = "Stop"

if (-not (Test-Path "docker-compose.yml")) { throw "Run this from the submissions\db2-locklens folder." }
if ((Test-Path ".env") -or (Test-Path ".env.db2")) {
    throw ".env or .env.db2 already exists. Edit them by hand (DB2_PASSWORD and DB2INST1_PASSWORD must match) or delete them first."
}

$secure = Read-Host "Choose a Db2 password (8-64 letters and digits only)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }

if ($plain -notmatch '^[A-Za-z0-9]{8,64}$') { throw "Use 8-64 letters and digits only (no symbols)." }

(Get-Content "db2.env.example") -replace "choose_a_password_here", $plain | Set-Content ".env.db2" -Encoding Ascii
(Get-Content ".env.example")    -replace "your_db2_password_here",  $plain | Set-Content ".env"     -Encoding Ascii

Write-Host "Created .env.db2 and .env with the same password (both are git-ignored)."
Write-Host "Next: docker compose up -d"
