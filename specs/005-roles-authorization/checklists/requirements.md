# Specification Quality Checklist: Roles and Authorization (Milestone 5)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-01
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Iteration 1**: one issue was found and fixed:

1. *Scope is clearly bounded*: Out of Scope said roles could not be granted through the website
   "now or later". That contradicts milestone 7, which moves teacher and student management into
   the application. The line now says that only administrator rights stay configuration-only
   permanently.

**Deliberate exceptions to "no implementation details"**:

- The requirements refer to settings by role. The concrete names (`TEACHER_EMAILS`,
  `STUDENT_EMAILS`, `ADMIN_EMAILS`, `sync: false`) appear only in Assumptions, where they are traced
  to the existing milestone 4 pattern. `plan.md` will fix them as its contract.
- FR-025 names the "forbidden" response status. This is the observable contract that the access
  tests assert, not a design choice.

**Choices made as documented defaults instead of clarification markers** (see Assumptions):

- Any role removal logs the person out everywhere, even if they keep other roles. This follows the
  technical requirements literally. Adding a role does not log anyone out.
- "At once" means at the restart that applies the new configuration. Reconciliation ends the
  sessions in the shared database before the new version serves traffic.
- After a role switch the person lands on the home page. After the first role choice they land on
  the originally requested page.
- The "access denied" page never switches role automatically.
- CSRF is revisited as the milestone 4 spec required: role choice and switch must not be
  forgeable cross-site (FR-021). The mechanism is left to `plan.md`.
- Milestone 4 sessions (no current role) are upgraded on their next request rather than ended.
- Teacher and student lists may be empty everywhere. A malformed entry refuses start in every
  environment, as the administrator list already does.

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
