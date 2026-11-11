# Final Submission Checklist

Work top to bottom. Items marked **YOU** cannot be done for you.

## 0. Check the deadline first
The organizers' `README.md` lists the hard deadline as **29 October 2026, 7:00 PM IST** (PR and Google
Form). That date is already past. Contact the organizers / community channel now to ask whether late
submissions or an extension apply; their README says deadline changes are announced there.

## 1. Fill the personal placeholders (YOU)
Nothing below was invented for you.

| File | Field | What to put |
|---|---|---|
| `submission.json` | `team.name` | Your name or team label (currently `REPLACE_WITH_YOUR_NAME (individual participant)`) |
| `submission.json` | `team.members[0].name` | Your full name (`REPLACE_WITH_YOUR_FULL_NAME`) |
| `submission.json` | `team.members[0].github` | Your GitHub username (`REPLACE_WITH_GITHUB_USERNAME`) |
| `submission.json` | `team.members[0].email` | Your email (`replace-with-your-email@example.com`) |
| `submission.json` | `project.repo_url` | Your fork URL, or leave `""` |
| `submission.json` | `project.video_url` | Video link after step 4, or leave `""` |
| `LICENSE` | line 3 | `Copyright (c) 2026 <your name>` (currently `REPLACE WITH YOUR NAME`) |

Find them with: `Select-String -Path submissions\db2-locklens\* -Pattern "REPLACE" -Recurse`
(the validator does not require these to be filled, but reviewers will expect real values).

## 2. Verify on your laptop (YOU)
Follow `WINDOWS_QUICKSTART.md`. Minimum before you tick the PR checklist:
- [ ] `docker compose up -d` works; `python locklens_cli.py test-connection --wait 900` says OK
- [ ] `python locklens_cli.py init-db` succeeds
- [ ] `pytest -v` passes (note any failure; the LangChain and Streamlit tests un-skip once installed)
- [ ] `$env:LOCKLENS_RUN_INTEGRATION="1"; pytest tests/integration -v -s` passes (real Db2)
- [ ] The two-session demo shows blocker, waiter, diagnostics and an incident, then resolves
- [ ] Fill section 5 of `FINAL_TEST_REPORT.md` with the real results. **If something fails, do not
      claim it works; fix it or document it under Known Limitations.**
- [ ] `python scripts/validate_submission.py submissions/db2-locklens` passes (no venv inside the folder)

## 3. Screenshots (YOU)
Save PNGs in `submissions/db2-locklens/docs/screenshots/` (keep the folder's `.gitkeep`):
1. `01-live-monitor.png` – Live Lock Monitor showing the wait
2. `02-blocking-graph.png` – Blocking Relationships graph
3. `03-diagnostics.png` – a WARNING finding expanded (evidence + next steps)
4. `04-incident-history.png` – one OPEN incident
5. `05-docker-db2.png` – `docker ps` showing `db2server (healthy)` (optional)
Blur nothing sensitive: the UI never displays the password, but check terminals for it.
Then reference them in the README "Screenshots & Demo" section if you want them shown.

## 4. Demo video (YOU)
- 2–3 minutes, screen + voice, using `DEMO_SCRIPT.md`; 1080p; audible narration.
- Upload to YouTube (unlisted is fine), Loom or Drive with *anyone with the link can view*.
- Paste the link into `submission.json` → `project.video_url` and into the PR description.

## 5. Copy the final project into your clone and commit (YOU)
Your clone has `origin` (your fork), `upstream` (official repo) and branch `submission/db2-locklens`.
Replace the two `<...>` values. This only copies `submissions\db2-locklens`; `.git` and the remotes are untouched.

```powershell
$Zip  = "$HOME\Downloads\IBM_Db2_TechX_Repository_FINAL.zip"
$Repo = "<C:\path\to\your\IBM_Db2_TechX_Project_Submission clone>"
$Tmp  = Join-Path $env:TEMP "locklens_final"

# extract to a temporary folder
if (Test-Path $Tmp) { Remove-Item $Tmp -Recurse -Force }
Expand-Archive -Path $Zip -DestinationPath $Tmp
$Src = Join-Path $Tmp "IBM_Db2_TechX_Repository\submissions\db2-locklens"
if (-not (Test-Path $Src)) { throw "Unexpected ZIP layout: $Src not found" }

# make sure you are on the right branch with remotes intact
Set-Location $Repo
git branch --show-current          # must print: submission/db2-locklens
git remote -v                      # origin = your fork, upstream = KunalGolaIBM/IBM_Db2_TechX_Project_Submission
git status --short                 # note any existing changes before copying

# copy ONLY the project folder (robocopy exit codes 0-7 mean success)
robocopy $Src "$Repo\submissions\db2-locklens" /E /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
Remove-Item "$Repo\submissions\db2-locklens\src\.gitkeep","$Repo\submissions\db2-locklens\tests\.gitkeep" -ErrorAction SilentlyContinue

# review exactly what changed; it must be ONLY submissions/db2-locklens/
git status --short
git diff --stat
python scripts\validate_submission.py submissions\db2-locklens

# commit and push the existing branch
git add submissions/db2-locklens
git status                         # confirm nothing outside submissions/db2-locklens is staged
git commit -m "feat(db2-locklens): add hackathon submission"
git push -u origin submission/db2-locklens
```
If you have already put a venv or `.env` files inside the folder: `.env*` are git-ignored, but move any
`.venv` out before running the validator.

## 6. Open the pull request (YOU)
Required by the organizers: base repo `KunalGolaIBM/IBM_Db2_TechX_Project_Submission`, base branch `main`,
head = your fork's `submission/db2-locklens`, title exactly:

```
[Submission] db2-locklens: Db2 LockLens – Explainable Lock & Deadlock Investigator
```
Web: your fork on GitHub → **Contribute → Open pull request**, then fill the template (suggested text below).
CLI alternative (needs GitHub CLI, `gh auth login` done; no PR exists until you run it):
```powershell
gh pr create --repo KunalGolaIBM/IBM_Db2_TechX_Project_Submission --base main `
  --head <your-github-username>:submission/db2-locklens `
  --title "[Submission] db2-locklens: Db2 LockLens – Explainable Lock & Deadlock Investigator" `
  --body-file pr_body.md
```
Check `git remote show upstream` shows `HEAD branch: main`; if it differs, use that as `--base`.

### Suggested PR description (paste into the template; edit the `<…>` parts)
```
## 1. Project Overview
- Project Title: Db2 LockLens – Explainable Database Lock & Deadlock Investigator
- Project Slug: submissions/db2-locklens/
- Short Description: A Streamlit dashboard that reads IBM Db2's native lock monitoring, identifies
  blocking and waiting applications, explains lock contention with evidence-based diagnostics, and
  stores an incident history in Db2.
- Problem Solved & Target Audience: Finding which transaction blocks others is slow and manual.
  Audience: DBAs, backend developers, SRE/DevOps teams running Db2.

## 2. Team Information
- Team Name: <your name>   (individual project)
- Members: <Full Name> | @<github-username> | <email> / Individual participant

## 3. IBM Db2 Integration Summary
- Edition: Db2 Community Edition on Docker
- Use: MON_GET_LOCKS, MON_GET_APPL_LOCKWAIT, MON_GET_CONNECTION, MON_FORMAT_LOCK_NAME for live data;
  a LOCKLENS.LOCK_INCIDENTS table (identity PK, unique index EXCLUDE NULL KEYS) for incident history
- Connector: ibm_db
- Schema & Data: incident records only; demo uses a disposable LOCKLENS_DEMO schema
- Steps to Verify: README → "Demonstration: two-session lock wait"; `pytest tests/integration`

## 4. Technology Stack & AI / LLM Usage
- Languages: Python, SQL
- Frameworks: Streamlit, Plotly, LangChain, pandas, Docker Compose
- AI/LLM Framework: LangChain (core pipeline); Model: none required; optional local Ollama model
- AI/LLM use: diagnosis is deterministic rules; LangChain composes the pipeline; an optional local model
  only summarises already-computed findings

## 5. Demonstration & Links
- Live Demo: not hosted (runs locally)
- Demo Video: <link>
- Slides: n/a

## 7. Notes for reviewers
See README "Honest verification status". Real-Db2 integration steps: <summarise what you actually ran>.
```
Only tick the template checkboxes that are true. In particular "Tested setup instructions" requires you to
have done step 2; the "Code of Conduct" box means you agree to `CODE_OF_CONDUCT.md`.

## 7. Submit the official form (YOU)
The organizers' repo states a PR alone does **not** complete the submission:
1. Copy the PR URL (`https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/pull/<number>`).
2. Open the **Google Form**. The link is still the placeholder `[GOOGLE_FORM_LINK_TO_BE_ADDED]` in the
   organizers' README and PR template, so get it from the organizers' announcement or community channel.
3. Enter your team details and paste the PR URL; submit; keep the confirmation.
4. **Unstop:** the repository does not mention Unstop. If your hackathon page on Unstop asks for a
   separate registration or a submission link, complete it too and paste the same PR URL there
   (I could not verify Unstop's current form fields).

## 8. After submitting
- [ ] Don't force-push or delete the branch; fix review comments with new commits on the same branch.
- [ ] Keep Docker/Db2 and the dashboard ready in case judges ask for a live demo.
