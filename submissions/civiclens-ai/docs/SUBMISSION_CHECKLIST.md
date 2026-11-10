# CivicLens AI: final submission checklist

Prepared on 9 November 2026 against the **official repository's current `main`** (`KunalGolaIBM/IBM_Db2_TechX_Project_Submission` at `4d685c2`, last commit 29 October 2026). Nothing below has been submitted: **no pull request has been opened and no form has been filled.**

Legend: ✅ verified by a check that was actually run · 🧑 needs you (a decision or a fact only you can supply) · ⛔ blocked

## 1. Where things stand

| Requirement (official source) | Status | Evidence / note |
|---|---|---|
| Folder `submissions/civiclens-ai/`, slug is lowercase kebab-case (`CONTRIBUTING.md`) | ✅ | matches `^[a-z0-9]+(-[a-z0-9]+)*$` and `submission.json → project.slug` |
| Required files: `README.md`, `architecture.md`, `submission.json`, `.env.example`, `src/` (`submissions/README.md`) | ✅ | all present; also `tests/`, `docs/screenshots/` |
| README follows the official template (14 sections) | ✅ | compared programmatically with `_template/README.md`: none missing |
| `architecture.md` follows the template (7 sections) | ✅ | plus extra sections |
| `submission.json` valid; required keys present | ✅ | official validator passes (`docs/evidence/submission_validator.txt`) |
| CI check (`.github/workflows/validate-submission.yml`: runs `scripts/validate_submission.py` for **every** submission on PRs to `main`) | ✅ | passes on the official repo today (3 folders) and with ours added (dry run: [`evidence/fresh_clone_run.txt`](evidence/fresh_clone_run.txt)) |
| Scope isolation: only `submissions/civiclens-ai/` changes | ✅ | 0 files outside the folder (`git diff --name-only main...HEAD`) |
| No secrets or credentials committed; `.env.example` placeholders only | ✅ | repo secret scan 0 findings (4 literal secrets checked); bundle scan 0 findings; no `.env`/key files; `pip-audit` and `npm audit --omit=dev`: 0 known vulnerabilities |
| Screenshots in `docs/screenshots/` | ✅ | 28 genuine captures + manifest (see `docs/screenshots/README.md`) |
| Setup instructions tested from a fresh environment | ✅ | new clone of the official `main`, new virtualenv and `node_modules` ([`evidence/fresh_clone_run.txt`](evidence/fresh_clone_run.txt)) |
| Third-party licences declared | ✅ | README, last section |
| Team member name | ✅ / 🧑 | **Tej Sagar**, the public display name of the GitHub account `tej-1916` (verified through GitHub). Please confirm it is the name you want on the submission |
| Team name | 🧑 | `CivicLens` is derived from the project name; nobody told me a different one. Confirm or change `team.name` in `submission.json` |
| Member e-mail | 🧑 optional | left empty on purpose (contact details are not published without your say-so). The PR template's table has an "Email / Role" column: add it there only if you want it public |
| Other team members | 🧑 | only one participant could be verified. If there are others, add them to `submission.json`, the README table and the PR |
| **Licence for the project's own code** | ✅ | MIT approved by the participant; see `LICENSE` in this project folder. |
| Code of Conduct | 🧑 | each member must agree to `CODE_OF_CONDUCT.md` (a checkbox in the PR) |
| Demo video | 🧑 | `docs/demo/civiclens-demo.mp4` is a captioned screen recording (silent). Upload it (YouTube/Loom/Drive) and put the link in the PR and `submission.json → project.video_url` if you want one, or record your own voice-over with `docs/DEMO.md` |
| Live demo URL | ➖ | none: not deployed. The app is **not safe to expose publicly yet** (public read endpoints, static tokens, no rate limiting); do not fill `demo_url` |
| Real-LLM verification | ⛔ | no provider credentials exist; no real LLM run was made. Everything is labelled rule-based or manual |
| Deadline | 🧑 | the repository README still says **29 Oct 2026, 7:00 PM IST**; your brief says **10 Nov 2026, 5:00 PM IST**. The repo shows no update, so confirm the later date in the official community channel |
| Google Form | 🧑 | the form link is still `[GOOGLE_FORM_LINK_TO_BE_ADDED]` in the official repo. Get it from the organisers; opening the PR is only step 1 |

## 2. Placeholders found in the project folder (all of them)

| Where | Text | Verdict |
|---|---|---|
| `submission.json` `team.members[0].name` | was `TODO: full name` | **fixed**: `Tej Sagar` (GitHub profile name); confirm |
| `README.md` team table | was `_To be completed by the team_` | **fixed**: same name |
| `submission.json` `team.name` | `CivicLens` | unverified, see above |
| `submission.json` `team.members[0].email` | empty | intentional |
| `submission.json` `project.demo_url`, `project.video_url` | empty | intentional until a verified URL exists |
| `.env.example` values (`change_me_…`, `your_…_here`) | placeholders | **required** by the rules (placeholders only) |
| `docs/PHASE_00_REPORT.md`, `PHASE_01A_REPORT.md`, `PHASE_01B_REPORT.md` | mention the old `TODO` | historical reports; each says what was true then |

No `TBD`, `FIXME`, `Insert URL` or template markers remain in `README.md` or `architecture.md`.

## 3. Licence: MIT approved and applied

The participant approved the MIT licence under Tej Sagar. `LICENSE` is included in the final submission branch. The following is the original reproducible example, not an action still required:

```bash
# MIT (permissive, common for hackathons)  -- or use Apache-2.0 from https://www.apache.org/licenses/LICENSE-2.0.txt
cat > submissions/civiclens-ai/LICENSE <<'EOF'
MIT License

Copyright (c) 2026 Tej Sagar

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
EOF
# and one line in the README, under "Team Members & Credits":
#   **Licence:** MIT, see [`LICENSE`](LICENSE). Third-party licences are listed below. All demo data is synthetic.
```

## 4. Final PR checklist (the official template's section 6, with my verification)

Tick only what is true for you when you open the PR.

- [x] **Folder Structure:** a single new directory `submissions/civiclens-ai/` (verified).
- [x] **Naming Conventions:** slug `civiclens-ai`; branch `submission/civiclens-ai`; title `[Submission] civiclens-ai: …` (the branch is created by the commands below).
- [x] **Complete Documentation:** `README.md` and `architecture.md` complete, no unfilled markers (verified; note the open items in section 1).
- [x] **Metadata File:** `submission.json` valid JSON, validator passes.
- [x] **No Secrets or Credentials:** scans clean (see evidence); `.env.example` placeholders only.
- [x] **Tested Setup Instructions:** run from a fresh clone ([`evidence/fresh_clone_run.txt`](evidence/fresh_clone_run.txt)).
- [x] **License Declared:** MIT (`LICENSE`), approved by the participant.
- [ ] **Code of Conduct:** 🧑 every member must agree.
- [x] **Scope Isolation:** only `submissions/civiclens-ai/` (re-check with the command in step 4 below).
- [ ] **Google Form Submission:** 🧑 you must do this after the PR exists.

## 5. Exact commands: create the final submission branch

Run them in **your clone of your fork** (`origin` = `https://github.com/tej-1916/IBM_Db2_TechX_Project_Submission`). They create **one clean commit authored by you** on a branch cut from the official `main`, so the PR contains only `submissions/civiclens-ai/`.

```bash
# 0. check where you are, and that your commit identity is yours
git remote -v
git config user.name && git config user.email

# 1. add the official repo as "upstream" (skip if it already exists), then fetch
git remote add upstream https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission.git
git fetch upstream main
git fetch origin feat/civiclens-final

# 2. the submission branch, cut from the OFFICIAL main (required name: submission/<project-slug>)
git checkout -b submission/civiclens-ai upstream/main

# 3. bring in ONLY the project folder from the finished work
git checkout origin/feat/civiclens-final -- submissions/civiclens-ai

# 4. scope and validator checks (the first command must print only the OK line; CI runs the validator without arguments)
git status --short | grep -v " submissions/civiclens-ai/" || echo "OK: only submissions/civiclens-ai/ changed"
python scripts/validate_submission.py
git ls-files -o --exclude-standard | head          # must be empty (no stray untracked files)

# 5. (optional) apply the licence from section 3 here, then commit once
git add submissions/civiclens-ai
git commit -m "feat(civiclens-ai): add CivicLens AI hackathon submission"
git push -u origin submission/civiclens-ai
```

Then open the pull request **from** `tej-1916/IBM_Db2_TechX_Project_Submission` branch `submission/civiclens-ai` **to** `KunalGolaIBM/IBM_Db2_TechX_Project_Submission` branch **`main`**:

* Title: `[Submission] civiclens-ai: CivicLens AI, Db2-backed urban infrastructure investigations`
* Body: paste [`PR_DESCRIPTION.md`](PR_DESCRIPTION.md) (it follows the official template) and tick the boxes that are true.
* Or with the GitHub CLI: `gh pr create --repo KunalGolaIBM/IBM_Db2_TechX_Project_Submission --base main --head tej-1916:submission/civiclens-ai --title "[Submission] civiclens-ai: CivicLens AI, Db2-backed urban infrastructure investigations" --body-file submissions/civiclens-ai/docs/PR_DESCRIPTION.md`

## 6. After the PR is open

1. Check the **Validate Project Submission** action turns green (it runs `scripts/validate_submission.py` for every submission). If it fails, open its log; the FAQ lists the usual causes (files outside the slug, missing files, invalid `submission.json`, a committed `.env`).
2. Copy the PR URL (`https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/pull/<number>`).
3. **Submit it in the official Google Form** (link from the organisers; the repository still shows a placeholder). A PR alone does not complete the submission.
4. You may keep pushing commits to `submission/civiclens-ai` until the deadline; the PR updates itself. Do not close and reopen it.
5. Publish the LinkedIn post from [`LINKEDIN_SUMMARY.md`](LINKEDIN_SUMMARY.md) if you want to (edit freely; it contains no claims beyond what was verified).

## 7. Time

The brief's deadline is **10 November 2026, 5:00 PM IST (11:30 UTC)**. At 18:10 UTC on 9 November roughly 17 hours remain. The steps in sections 3 to 6 take about 15 minutes.
