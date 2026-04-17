# AI Instruction Bootstrap

This project has been initialized with a standard AI instruction policy for:

- GitHub Copilot
- path-specific instructions
- general coding agents
- Claude-style agent guidance
- browser validation expectations
- Playwright-ready test folder
- optional Flask enterprise baseline

## Installed files

- .github/copilot-instructions.md
- .github/instructions/kluster-code-verify.instructions.md
- .github/instructions/frontend.instructions.md
- .github/instructions/backend.instructions.md
- .github/instructions/security.instructions.md
- AGENTS.md
- CLAUDE.md
- .vscode/settings.json
- .vscode/extensions.json

## Recommended next steps

1. Install dependencies for your stack.
2. Add Playwright if your app has UI:
   - JavaScript/TypeScript: npm init playwright@latest
   - Python: pip install playwright && playwright install
3. Add CI validation for lint, tests, and E2E.
4. Use this repo as a template for future projects.

Project: DoApp
