# PayGuard demo recording script (about 3 minutes)

Record at 1080p with the browser at 100% zoom. On Windows, press **Win + Alt + R** (Xbox Game Bar) to start and stop, or use OBS. Speak slowly; one take per scene is fine, then join them.

Before recording: run `start.bat`, open http://localhost:8000, and check that http://localhost:8000/api/health shows `"db2": true`.

| # | Time | What to show | What to say |
|---|---|---|---|
| 1 | 0:00-0:20 | Home page | "Nigerians lose billions to the same scam scripts. PayGuard checks a seller before your money leaves." |
| 2 | 0:20-0:55 | Drag `docs/demo/sample-chat.png` onto the page, click **Check now** | "I just share a screenshot of the chat. Gemini reads the seller, the account number and the Pidgin, and PayGuard says: don't pay. Three plain reasons." |
| 3 | 0:55-1:10 | Switch to **Pidgin**, then click **Real shop** and check it | "Same answer in Pidgin. And a genuine shop passes." |
| 4 | 1:10-1:35 | Open **Technical details** on the scam verdict | "Behind it is IBM Db2: a blocklist, and vector search over 25 scam playbooks and community reports using Db2's VECTOR type and VECTOR_DISTANCE." |
| 5 | 1:35-1:55 | **Report a scam**: report the same contact | "Every report goes into Db2. Three reports block a contact automatically with one MERGE statement." |
| 6 | 1:55-2:25 | **For platforms** (`/market`): Buy the PS5, then the textbook | "Marketplaces call our API when the buyer taps Pay. The scam seller is stopped; the real bookshop goes on to PayPal." |
| 7 | 2:25-2:45 | **Shopping agent**: click **Ticket seller**, then **Safe order** | "An AI shopping agent can't be tricked either. It refuses the ticket scam and prepares PayPal checkout for the safe order." |
| 8 | 2:45-3:00 | **Dashboard**: ask "Which payment method has the highest average risk?" | "Analysts ask questions in English; PayGuard writes guarded, read-only Db2 SQL. Next: Truecaller for account numbers. Thank you." |

## Per hackathon
- **IBM Db2Hack:** give scenes 4, 5 and 8 more time (Db2 features).
- **PayPal AI Hackathon:** give scenes 6 and 7 more time. The PayPal buttons only appear after you add `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` (sandbox) to `.env` and restart.

Check each hackathon page for its video length limit before uploading.
