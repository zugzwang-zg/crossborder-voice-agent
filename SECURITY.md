# Security policy

## Reporting

Please report suspected credential exposure or security-sensitive data leakage
privately to the repository maintainer rather than opening a public issue.

## Sensitive material

Never commit:

- API keys, access tokens, `.env` files, or provider credentials;
- private or licensed review datasets not approved for redistribution;
- reviewer identities, private annotations, raw API logs, or billing details.

Use `.env.example` for configuration names and synthetic or approved public
samples for tests. If a secret is committed, revoke it immediately and remove
it from the repository history before publishing a replacement.

Automated insight output is not a security, legal, medical, or market-approval
decision and must retain its source and sampling boundaries.
