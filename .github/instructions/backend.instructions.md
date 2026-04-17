---
applyTo: "backend/**,api/**,server/**,src/**/*.py,src/**/*.js,src/**/*.ts,controllers/**,services/**,routes/**,repositories/**"
---

Backend rules:
- Trace request flow end-to-end before changing logic.
- Preserve authentication and authorization boundaries.
- Validate all inputs.
- Use safe data access patterns and parameterized queries.
- Assess API contract compatibility.
- Assess performance, concurrency, and regression risks.
- Add or update tests for business rules, unhappy paths, and security-sensitive cases.
