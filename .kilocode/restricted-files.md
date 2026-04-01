# Restricted Files

- Do not modify or overwrite restricted files unless explicitly instructed.
- If a task requires changes to a restricted file, ask for confirmation before proceeding.

- Treat the following as restricted by default:
  - Environment/config files (e.g., .env)
  - Dependency definitions (e.g., requirements, lock files)
  - Infrastructure and deployment configs
  - Database schemas and migrations
  - Authentication and security-related code

- Do not introduce breaking changes to public interfaces or shared modules without explicit approval.

- When suggesting changes to restricted files:
  - Clearly explain the reason
  - Highlight potential risks
  - Provide a minimal, safe modification

- Prefer additive changes over destructive ones.
- Do not delete or rename critical files without confirmation.

- Avoid exposing or modifying secrets, credentials, or sensitive data.

- If unsure whether a file is restricted, treat it as restricted by default.