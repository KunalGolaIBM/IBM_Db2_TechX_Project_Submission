# Security Policy

Odyssey is an actively developed open-source project. Security reports are welcome, and responsible reporting helps protect contributors and users.

## Supported Versions

Security fixes are generally developed against the latest version on the default branch.

Older versions and unofficial deployments may not receive security updates. If you are using a deployed instance, verify which version it runs before assuming a fix is available.

## Reporting a Vulnerability

**Please do not report suspected security vulnerabilities through public issues or pull requests.**

Instead, contact the maintainer privately through the contact method listed on the repository's GitHub profile. If GitHub's private vulnerability reporting feature is enabled for this repository, you may use that channel.

When reporting a vulnerability, include as much of the following information as you can safely provide:

- A concise description of the suspected vulnerability.
- The affected component, route, function, or workflow.
- The potential impact.
- Steps to reproduce the issue or a minimal proof of concept.
- The affected commit, version, or deployment, if known.
- Suggested mitigations, if available.

Please report only the information necessary to explain the issue. Do not include real user data, passwords, API keys, access tokens, or other secrets in a report.

## What to Expect

The maintainer will review the report and may request additional information to understand its scope and impact.

Please allow reasonable time for investigation and remediation before disclosing the vulnerability publicly. A particular response or resolution timeline is not guaranteed.

Once a fix or mitigation is available, the maintainer may publish an update or security advisory as appropriate.

## Security Considerations

When developing or deploying Odyssey:

- Never commit `.env` files or expose server-side secrets in client-side code.
- Keep Gemini API keys and Supabase service-role keys on the server side.
- Use the Supabase publishable key only with appropriate authentication, database permissions, and Row Level Security policies.
- Validate and authorize requests to backend services and Edge Functions.
- Avoid logging credentials, sensitive user content, or private data.
- Review third-party dependencies and configuration changes for security implications.

These guidelines are not a substitute for a security review of a deployment or its configuration.