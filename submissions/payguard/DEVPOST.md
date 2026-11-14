# PayGuard: Devpost submission text (copy each part into the matching box)

## Project name
PayGuard

## Tagline (short)
An AI payment firewall on IBM Db2: check a seller before your money leaves.

## Inspiration
In Nigeria, almost everyone knows someone who paid for a phone on Instagram and never got it. The scripts repeat: "pay as friends and family", "send to my OPay", "your PayPal is limited", "pay a registration fee for the job". Social engineering was 47% of fraud in Nigeria in 2025 (NIBSS). Fraud checks usually run after the money moves. We wanted a check that happens before it.

## What it does
- **Check a seller:** share a screenshot of the chat or paste it. PayGuard answers Safe, Be careful, or Don't pay, with at most three plain reasons, in English or Nigerian Pidgin.
- **Report a scam:** reports go into Db2. Three reports block an account or phone number automatically.
- **Protected checkout for platforms:** a marketplace calls the PayGuard API when the buyer taps Pay. Scam sellers are stopped; safe orders go on to PayPal checkout.
- **AI shopping agent:** "buy X from Y for $Z". The agent builds the order, screens it, and refuses or prepares PayPal checkout.
- **Fraud dashboard:** live numbers, and questions in plain English turned into guarded, read-only Db2 SQL.

## How we built it
- **IBM Db2 12.1 (Docker):** VECTOR(768) columns and VECTOR_DISTANCE cosine search over 25 scam playbooks and community reports; hybrid vector + relational filtering; MERGE upserts that auto-escalate a contact to BLOCKED after 3 reports; FINAL TABLE generated keys; analytics views; SYSCAT introspection for text-to-SQL.
- **AI:** Google Gemini for screenshot reading (vision), an investigator agent whose tools are Db2 queries, and the shopping agent. The AI can raise risk or explain it, but never lower a verdict.
- **PayPal:** Orders v2 (sandbox) on the server plus the PayPal JS SDK. The server re-reads the verdict from Db2 before creating any order, so a blocked payment can't be forced through from the browser.
- **App:** Python, FastAPI, plain HTML/CSS/JS, installable as a web app (Android share target). 31 automated tests.

## Challenges we ran into
Keeping the AI from overruling the evidence (solved by letting it only raise risk), writing safe text-to-SQL (single read-only SELECT, PayGuard tables only, forced row limits, rolled back), and making the answer simple enough for a buyer in a hurry.

## Accomplishments that we're proud of
A buyer gets a clear answer in seconds, in Pidgin if they want, without copying anything. And the same check plugs into a marketplace checkout in one API call.

## What we learned
Db2's vector search lets the scam knowledge base and the account blocklist live in one database and one query. Simple language matters as much as accuracy.

## What's next
A WhatsApp bot (forward a chat or voice note), a browser extension, and checking at the moment of transfer: a "Truecaller for account numbers" that banks and fintechs call when a user types a recipient's account number.

## Built with
ibm-db2, python, fastapi, google-gemini, paypal, javascript, html, css, docker, sql

## Links
- GitHub: https://github.com/Josebert2001/payguard
- Video: (YouTube link after upload)
