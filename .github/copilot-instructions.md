# Copilot Repository Instructions

Project: DoApp

You are working in a production-grade software project.

## Mandatory workflow
- First understand the relevant architecture, data flow, auth flow, UI flow, dependencies, and impacted modules before changing code.
- Never make blind edits or isolated fixes without tracing upstream and downstream impact.
- Before implementation, restate the requirement clearly:
  - current behavior
  - required behavior
  - assumptions
  - constraints
  - edge cases
  - acceptance criteria
  - out-of-scope items
- Propose a concise implementation plan before coding.
- Prefer root-cause fixes over superficial patches.
- Make minimal, focused, maintainable changes aligned to existing patterns unless a justified architectural correction is required.

## Security requirements
For every change, perform a security review appropriate to the stack and feature. Check for:
- authentication and authorization issues
- privilege escalation / IDOR
- injection risks
- XSS / CSRF / SSRF
- insecure file handling
- secrets exposure
- sensitive data leakage
- insecure logging
- tenant isolation violations
- unsafe defaults
- broken validation
- business logic abuse
- dependency and configuration risk

If a requested implementation is insecure, do not implement it as-is.
Implement the secure version and explain why.

## Testing requirements
- Run relevant linting, static analysis, and type checks.
- Run unit, integration, API, and end-to-end tests where applicable.
- Do not declare completion without validation evidence.

## UI/browser validation
For any UI-facing change:
- run the app
- open the browser
- validate the affected workflow end-to-end
- verify UI/UX, validation, loading, error, success, and permission states
- check browser console issues
- test using Playwright where applicable
- retest until the confirmed requirement is satisfied

## Response format
Always structure work as:
1. Understanding
2. Requirement confirmation
3. Risk and security analysis
4. Implementation plan
5. Changes made
6. Tests run
7. Browser/Playwright validation results
8. Final status

A task is not complete until implementation, testing, and validation are all done.
