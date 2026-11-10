<#
.SYNOPSIS
  NEEDLE team pipeline on Windows (Windows PowerShell 5.1 or PowerShell 7). Runs the selected steps in order
  and stops at the first failure.

.DESCRIPTION
  Steps in "all" order:
    ingest    python -m needle.ingest_osv              -> data/docs.jsonl, data/raw.jsonl.gz
    embed     python -m needle.embed                   -> data/emb.jsonl.gz (Ollama nomic-embed-text, resume-safe)
    bm25      python -m needle.bm25 build              -> data/postings.jsonl.gz, data/corpus_stats.json
    load      bash scripts/load_in_codespace.sh        bulk load runs INSIDE the Codespace (never through the tunnel)
    postings  bash scripts/load_postings_in_codespace.sh
    queries   python eval/build_queries.py --verify    checks the frozen query-file hashes
    test      python -m pytest -q -m "not db"          Db2-free unit tests
    eval      python eval/run_eval.py                  needs Db2 reachable at DB2_HOST:DB2_PORT and Ollama
  Explicit-only steps (never part of "all"):
    users     create the RCAC analyst users in the Codespace container (scripts/rcac_users.sh; passwords via stdin)
    testdb    python -m pytest -q -m db                Db2 integration tests
    app       python -m streamlit run src/needle/app.py
    validate  copy this folder into a clone of the official submission repo and run its validator

  A step whose script or module does not exist yet is skipped with a warning.
  This script never reads or prints a password. Only the CODESPACE and APP_PORT keys are read from .env.

.PARAMETER Step
  One or more step names, e.g. -Step embed,bm25. Default: all.

.PARAMETER ValidateRepo
  Path to a local clone of KunalGolaIBM/IBM_Db2_TechX_Project_Submission (needed by -Step validate).

.PARAMETER Evidence
  Also save the output of test, testdb, eval and validate to docs/evidence/<step>.txt (UTF-8).

.EXAMPLE
  .\scripts\run_all.ps1 -Step ingest,embed,bm25
.EXAMPLE
  .\scripts\run_all.ps1 -Step validate -ValidateRepo C:\work\IBM_Db2_TechX_Project_Submission -Evidence
#>
[CmdletBinding()]
param(
  [ValidateSet('all', 'ingest', 'embed', 'bm25', 'load', 'postings', 'queries', 'test', 'eval',
               'users', 'testdb', 'app', 'validate')]
  [string[]]$Step = @('all'),
  [string]$ValidateRepo = '',
  [switch]$Evidence
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$EvidenceDir = Join-Path $Root 'docs\evidence'
$AllSteps = @('ingest', 'embed', 'bm25', 'load', 'postings', 'queries', 'test', 'eval')

function Write-Step([string]$Text) { Write-Host ("[run_all {0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Text) }

function Get-EnvKey([string]$Key, [string]$Default = '') {
  # Reads one non-secret key from .env. Never used for passwords.
  $envFile = Join-Path $Root '.env'
  if (-not (Test-Path $envFile)) { return $Default }
  $line = Get-Content $envFile | Where-Object { $_ -match ('^' + [regex]::Escape($Key) + '=') } | Select-Object -Last 1
  if ($null -eq $line) { return $Default }
  $val = ($line -replace ('^' + [regex]::Escape($Key) + '='), '').Trim().Trim('"').Trim("'")
  if ($val -eq '') { return $Default }
  return $val
}

function Get-Bash {
  $candidates = @(
    (Join-Path $env:ProgramFiles 'Git\bin\bash.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Git\bin\bash.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe')
  )
  foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
  throw 'Git Bash not found. Install Git for Windows (bash.exe is used for the Codespace wrappers).'
}

function Test-Present([string]$RelPath, [string]$StepName) {
  if (Test-Path (Join-Path $Root $RelPath)) { return $true }
  Write-Warning ("SKIP {0}: {1} does not exist yet." -f $StepName, $RelPath)
  return $false
}

function Invoke-Native {
  param([string]$Exe, [string[]]$Arguments, [string]$Name, [switch]$Capture)
  Write-Step ("{0}: {1} {2}" -f $Name, (Split-Path -Leaf $Exe), ($Arguments -join ' '))
  if ($Capture -and $Evidence) {
    $out = & $Exe @Arguments
    $code = $LASTEXITCODE
    $out | ForEach-Object { Write-Host $_ }
    if (-not (Test-Path $EvidenceDir)) { New-Item -ItemType Directory -Force $EvidenceDir | Out-Null }
    $file = Join-Path $EvidenceDir ("{0}.txt" -f $Name)
    $header = @(
      ("# {0}  (run {1} local time)" -f $Name, (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
      ("# command: {0} {1}" -f (Split-Path -Leaf $Exe), ($Arguments -join ' ')),
      ("# exit code: {0}" -f $code),
      ''
    )
    [System.IO.File]::WriteAllLines($file, [string[]]($header + @($out | ForEach-Object { "$_" })))
    Write-Step ("{0}: output saved to {1}" -f $Name, $file)
  } else {
    & $Exe @Arguments
    $code = $LASTEXITCODE
  }
  if ($code -ne 0) { throw ("{0} failed with exit code {1}." -f $Name, $code) }
}

# ------------------------------------------------------------------------------------------------
$selected = New-Object System.Collections.Generic.List[string]
foreach ($s in $Step) {
  if ($s -eq 'all') { $AllSteps | ForEach-Object { if (-not $selected.Contains($_)) { $selected.Add($_) } } }
  elseif (-not $selected.Contains($s)) { $selected.Add($s) }
}

if (-not (Test-Path $Py)) { throw ("Python venv not found at {0}. Create it: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" -f $Py) }
$env:PYTHONPATH = Join-Path $Root 'src'

Push-Location $Root
try {
  foreach ($s in $selected) {
    switch ($s) {
      'ingest' {
        if (Test-Present 'src\needle\ingest_osv.py' $s) { Invoke-Native $Py @('-m', 'needle.ingest_osv') $s }
      }
      'embed' {
        if (Test-Present 'src\needle\embed.py' $s) { Invoke-Native $Py @('-m', 'needle.embed') $s }
      }
      'bm25' {
        if (Test-Present 'src\needle\bm25.py' $s) { Invoke-Native $Py @('-m', 'needle.bm25', 'build') $s }
      }
      'load' {
        if (Test-Present 'scripts\load_in_codespace.sh' $s) {
          if ((Get-EnvKey 'CODESPACE') -eq '') { throw 'Set CODESPACE in .env for the load step.' }
          Invoke-Native (Get-Bash) @('scripts/load_in_codespace.sh') $s
        }
      }
      'postings' {
        if (Test-Present 'scripts\load_postings_in_codespace.sh' $s) {
          if ((Get-EnvKey 'CODESPACE') -eq '') { throw 'Set CODESPACE in .env for the postings step.' }
          Invoke-Native (Get-Bash) @('scripts/load_postings_in_codespace.sh') $s
        }
      }
      'queries' {
        if (Test-Present 'eval\build_queries.py' $s) { Invoke-Native $Py @('eval\build_queries.py', '--verify') $s }
      }
      'test' {
        if (Test-Present 'tests' $s) { Invoke-Native $Py @('-m', 'pytest', '-q', '-m', 'not db', 'tests') 'pytest' -Capture }
      }
      'testdb' {
        if (Test-Present 'tests' $s) { Invoke-Native $Py @('-m', 'pytest', '-q', '-m', 'db', 'tests') 'pytest_db' -Capture }
      }
      'eval' {
        if (Test-Present 'eval\run_eval.py' $s) { Invoke-Native $Py @('eval\run_eval.py') 'eval' -Capture }
      }
      'users' {
        if (Test-Present 'scripts\rcac_users.sh' $s) {
          $cs = Get-EnvKey 'CODESPACE'
          if ($cs -notmatch '^[A-Za-z0-9-]+$') { throw 'Set CODESPACE in .env (letters, digits, hyphens).' }
          # The NDL_*_PASSWORD lines travel from .env to the remote script on stdin, inside bash.
          $cmd = "gh codespace ssh -c $cs -- 'mkdir -p ~/ndl_rcac' && " +
                 "gh codespace cp -c $cs -e scripts/rcac_users.sh remote:/home/codespace/ndl_rcac/rcac_users.sh && " +
                 "grep -E '^NDL_[A-Z0-9]+_PASSWORD=' .env | gh codespace ssh -c $cs -- 'bash ~/ndl_rcac/rcac_users.sh'"
          Invoke-Native (Get-Bash) @('-c', $cmd) $s
        }
      }
      'app' {
        if (Test-Present 'src\needle\app.py' $s) {
          $port = Get-EnvKey 'APP_PORT' '8501'
          if ($port -notmatch '^[0-9]{2,5}$') { $port = '8501' }
          Invoke-Native $Py @('-m', 'streamlit', 'run', 'src\needle\app.py', '--server.port', $port) $s
        }
      }
      'validate' {
        if ($ValidateRepo -eq '' -or -not (Test-Path (Join-Path $ValidateRepo 'scripts\validate_submission.py'))) {
          throw 'Pass -ValidateRepo <path to a clone of IBM_Db2_TechX_Project_Submission>.'
        }
        $dest = Join-Path $ValidateRepo 'submissions\needle'
        if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
        Write-Step ("validate: copying to {0} (without .env, .venv, data, caches)" -f $dest)
        & robocopy $Root $dest /E /XD .venv data __pycache__ .pytest_cache .mypy_cache /XF .env *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw ("robocopy failed with exit code {0}." -f $LASTEXITCODE) }
        $global:LASTEXITCODE = 0
        foreach ($bad in @('.env', '.venv', 'data')) {
          if (Test-Path (Join-Path $dest $bad)) { throw ("{0} was copied into the submission folder." -f $bad) }
        }
        Push-Location $ValidateRepo
        try { Invoke-Native $Py @('-X', 'utf8', '-I', 'scripts\validate_submission.py') 'validator' -Capture }
        finally { Pop-Location }
      }
    }
  }
  Write-Step ('done: ' + ($selected -join ', '))
}
finally {
  Pop-Location
}
