# How to submit (checklist)

1. Fork https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission on GitHub.
2. `git clone https://github.com/<you>/IBM_Db2_TechX_Project_Submission && cd IBM_Db2_TechX_Project_Submission`
3. `git checkout -b submission/quantummedx`
4. Copy this folder to `submissions/quantummedx/`. Do not copy `.env`, `node_modules`, `dist` or `storage`.
5. Edit `submissions/quantummedx/submission.json`: your GitHub username, email, and `repo_url` (your fork).
6. Add real screenshots of your running app to `submissions/quantummedx/docs/screenshots/` and link them in the README.
7. Fill in the run log in `docs/TESTING.md` with your own Db2 and test output.
8. `python scripts/validate_submission.py submissions/quantummedx` must say PASSED.
9. Confirm `git status` shows changes only under `submissions/quantummedx/` and no secrets (`git grep -i password` should show placeholders only).
10. Commit, push, and open a pull request to the original repository. Follow the PR title format in the repo's CONTRIBUTING.md.
11. Submit the PR URL in the Google Form: https://forms.gle/n8GQL4tg7Yzftwu39
12. Upload the Round 1 proposal PDF on Unstop if Round 1 is still open.
13. Post your LinkedIn update (draft in `docs/LINKEDIN_POST.md`) and tag the organisers.

Deadline: 10 November 2026, 5:00 PM IST. Aim to finish by midday.
