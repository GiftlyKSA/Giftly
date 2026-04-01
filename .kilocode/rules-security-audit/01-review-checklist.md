# Security Review Checklist

- Check for secrets and credentials hardcoded in source or config files.
- Validate all input entry points: user input, file uploads, environment variables, API responses.
- Review auth and authz logic: authentication bypass, broken access control, privilege escalation.
- Inspect error messages — they must not leak stack traces, internal paths, or system info to clients.
- Check dependency versions for known CVEs.
