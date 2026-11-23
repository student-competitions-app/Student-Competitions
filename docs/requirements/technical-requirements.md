# Technical Requirements

## Technology Stack

| Area | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-side rendering: Jinja2 + HTMX + Pico.css |
| Database | SQLite locally, PostgreSQL in production, via SQLModel + Alembic |
| Authentication | Email code (OTP) + server-side sessions in a signed cookie |
| Localisation | gettext catalogues managed with Babel (Jinja2 `jinja2.ext.i18n`); Ukrainian by default, English as the alternative |
| PDF files | PDF made on the server by one Python library (chosen in milestone 12.8's plan), fonts embedded. Results files are made once at publishing and stored in the database; a competition's questions file and a subject's study materials (milestone 12.10) are made at download and not stored, and the study materials may be kept in the application's memory but are never served stale |
| Answer evaluation | LLM API call (Claude or OpenAI) with structured output |
| Infrastructure & deployment | Docker + Render (or Railway / Fly.io) |
| Tooling & tests | uv, ruff, pytest, later Playwright |
| Development process | GitHub Spec Kit |
