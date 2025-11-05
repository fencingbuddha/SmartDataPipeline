# Week 11 — Bug Summary

| ID   | Area        | Symptom/Steps                                                 | Root Cause (initial)                          | Fix/Owner | PR | Status |
|------|-------------|---------------------------------------------------------------|-----------------------------------------------|-----------|----|--------|
| B-001| UI Visual   | `dashboard.visual.cy.ts` baseline mismatch (0 diff threshold) | Visual baseline out-of-date after UI changes  | Cameron   | —  | Open   |

## Evidence
- Cypress run: 9 specs / 23 tests, 1 failing - ![alt text](image.png)

