# Specification Quality Checklist: Email Code Authentication (Milestone 4)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-29
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

**Iteration 1**: issues found and fixed:

1. *Measurable outcomes*: SC-005 claimed a guessing chance "below 0.01% per address per day".
   With 5 attempts per code and 5 codes per hour, an attacker gets 600 guesses a day against 10⁶
   codes, which is 0.06%. Corrected to "below 0.1%" with the arithmetic stated.
2. *No implementation details*: Out of Scope named the partial-page library; reworded by role.

**Deliberate exceptions to "no implementation details"**:

- The requirements refer to settings, the email provider and the page-interactivity library by
  role. The concrete names (`EMAIL_BACKEND`, `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`,
  `EMAIL_FROM`, Resend, HTMX) appear only in Assumptions. That is where they are traced back to the
  binding technical requirements, and `plan.md` will fix them as its contract.
- FR-036 requires the provider's web API rather than a mail-server connection. This is an
  operational constraint (free hosting tiers block outbound mail ports), not a design preference.

**Choices made as documented defaults instead of clarification markers** (see Assumptions):

- CSRF: a same-site-restricted session cookie counts as sufficient for this milestone, as the
  technical requirements state. The residual login-CSRF risk is accepted, and milestone 5 must
  revisit CSRF. This reconciles the requirements with constitution Principle V. `/speckit-plan`
  should record it in the Constitution Check.
- Per-client rate limit (FR-018) is added beyond the technical requirements because constitution
  Principle V requires limits "per email and per client".
- The production start also refuses the in-memory delivery mode, not only console (FR-041),
  because it would silently drop every login email.
- Numeric defaults: 6-digit code, 20 min validity, 5 attempts per code, 5 requests per email per
  hour, 20 per client per hour, 14-day absolute sessions, 32-character minimum secret.
- Newest code invalidates older ones. Users are deactivated rather than deleted. Email addresses
  are kept out of logs.

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
