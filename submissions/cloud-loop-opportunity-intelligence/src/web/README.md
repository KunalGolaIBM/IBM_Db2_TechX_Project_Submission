# Cloud Loop — Student Opportunity Discovery Platform

**Cloud Loop** is the single place students go to discover every opportunity — programs, events, internships, jobs, and certifications — instead of checking a dozen different websites.

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Animations:** Framer Motion
- **Icons:** Lucide React
- **Auth:** Clerk
- **Theme:** next-themes (system-aware dark/light mode)

## Getting Started

```bash
cd cloud-loop-app
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

Copy `.env.local` and fill in:

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key |
| `CLERK_SECRET_KEY` | Clerk secret key |
| `NEXT_PUBLIC_APP_URL` | App URL (e.g. https://cloudloop.dev) |

## Deploy on Vercel

1. Push to GitHub
2. Import the `cloud-loop-app` folder in Vercel
3. Add environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
   - `CLERK_SECRET_KEY`
   - `NEXT_PUBLIC_APP_URL`
4. Deploy

## Pages

| Route | Description |
|---|---|
| `/` | Homepage with hero, featured opportunities, all sections |
| `/programs` | Filterable programs grid (Google, MLSA, GSoC, etc.) |
| `/programs/[slug]` | Program detail page |
| `/events` | Hackathons, bootcamps, conferences |
| `/internships` | Internship listings with filters |
| `/jobs` | Entry-level jobs with category tabs |
| `/certifications` | Industry certifications (Google, AWS, Microsoft…) |
| `/community` | Discord, Telegram, leaderboard |
| `/dashboard` | User dashboard (Clerk-protected) |
