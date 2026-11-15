# Contributing to Odyssey 🧭

Thank you for your interest in contributing to Odyssey!

Odyssey is an actively developed open-source productivity and execution application. Contributions that make its planning workflow more useful, reliable, accessible, and understandable are welcome.

You can contribute through code, documentation, testing, accessibility improvements, design feedback, bug reports, or focused feature proposals.

## Before You Start

1. Read the [README](README.md) to understand the project and its setup.
2. Review the [Code of Conduct](CODE_OF_CONDUCT.md).
3. Check existing issues and pull requests before starting new work.
4. For significant changes, open an issue or discuss the proposal with the maintainer first.

For your first contribution, consider a focused bug fix, documentation improvement, test, or clearly scoped enhancement.

## Choosing an Issue

When selecting an issue:

- Check whether it is already being addressed.
- Clarify expected behavior before implementing a substantial change.
- Keep the scope manageable and aligned with Odyssey's current direction.
- Ask questions when requirements or implementation details are unclear.

Please avoid starting large architectural changes without prior discussion.

## Development Setup

### Requirements

- Node.js 20 or newer
- npm
- A Supabase project for features requiring authentication or persistence
- A Gemini API key for AI-powered suggestions

### Local Setup

```bash
git clone https://github.com/aaliya1719/Odyssey.git
cd Odyssey
npm install
```

Create a local `.env` file from `.env.example`, then configure the required environment variables.

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Start the application:

```bash
npm run dev
```

Some UI work can be performed without connecting every external service. Changes involving authentication, database operations, or AI suggestions may require additional configuration. See the [README](README.md) for setup details.

## Making Changes

- Follow the existing project structure and coding conventions.
- Keep each change focused on a clear problem or improvement.
- Reuse existing components and utilities where appropriate.
- Avoid introducing unnecessary dependencies.
- Handle loading, empty, error, and relevant edge states.
- Consider accessibility, responsive layouts, and keyboard interaction.
- Keep secrets, personal data, generated output, and local configuration out of commits.
- Update documentation when behavior, setup, or configuration changes.

For AI-assisted contributions, review the generated code carefully and make sure you understand the behavior being introduced.

## Testing Your Changes

Run the relevant checks available in the repository:

```bash
npm run build
npm run lint
npm test
```

If a command is unavailable, check `package.json` for the scripts supported by your checkout.

For behavior changes, add or update tests where appropriate. Manually verify relevant user flows when automated coverage does not capture the change.

In your pull request, disclose any checks that could not be run and explain why. Do not claim tests passed unless you actually ran them.

## Submitting a Pull Request

Before opening a pull request:

1. Ensure your branch contains only the changes relevant to the contribution.
2. Review the diff and remove accidental or unrelated edits.
3. Run the relevant checks.
4. Update documentation or tests where necessary.
5. Describe the problem, your solution, and how you verified it.

A useful pull request description includes:

- **What:** A short summary of the changes.
- **Why:** The issue or user problem being addressed.
- **Verification:** Tests or manual checks performed.
- **Additional context:** Screenshots for UI changes, relevant limitations, or follow-up work.

Keep pull requests focused and reasonably sized so they can be reviewed effectively.

## Review Process

The maintainer may request clarification, revisions, additional tests, or a narrower scope. Changes may be declined if they introduce security risks, conflict with the project's direction, or cannot be maintained.

Please be constructive during reviews and allow time for feedback. Opening a pull request does not guarantee acceptance or a particular review timeline.

## Security

Do not include API keys, passwords, service-role credentials, private user data, or other secrets in issues, commits, or pull requests.

Report suspected vulnerabilities privately according to [SECURITY.md](SECURITY.md).

## Community Standards

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

Thank you for helping make Odyssey better!