# Contributing to TradeWise

Thank you for your interest in contributing to TradeWise! This guide explains how to get started.

## Getting Started

1. Fork the repository and clone your fork.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes following the conventions below.
4. Run the backend tests: `cd backend && python -m pytest tests/ -v`
5. Commit with a clear message and push your branch.
6. Open a Pull Request against `main`.

## Repository Structure

```
TradeWise/
├── backend/          # Python / Flask API
├── frontend/         # Vanilla JS frontend (no build tools)
│   ├── shared/       # Shared CSS, JS, and assets
│   ├── admin/        # Admin role pages
│   ├── learner/      # Learner role pages
│   └── pro-trader/   # Pro Trader role pages
├── supabase/         # Database schema and policies
└── docs/             # Technical documentation
```

## Code Conventions

### Backend (Python / Flask)
- Follow [PEP 8](https://peps.python.org/pep-0008/).
- Place new routes in `backend/app/routes/` as a Flask Blueprint.
- Place new models in `backend/app/models/` and export from `models/__init__.py`.
- All protected endpoints must use `@require_auth` (or the appropriate role decorator) from `app.middleware`.
- Add tests in `backend/tests/` for any new route or utility.

### Frontend (Vanilla JS / HTML / CSS)
- No build tools — write plain HTML, CSS, and JavaScript.
- Shared styles belong in `frontend/shared/css/`; role-specific styles in the respective `css/` sub-folder.
- Shared scripts belong in `frontend/shared/js/`.
- Always reference shared assets with the correct relative path (e.g., `../../shared/css/globals.css` from a `pages/` directory two levels deep).

### Database (Supabase / PostgreSQL)
- Schema changes must be added as a new numbered migration file in `supabase/migrations/`.
- Keep `supabase/rls-policies.sql` up to date with any new table's Row Level Security policy.

## Commit Messages

Use the format: `<type>: <short description>`

| Type       | When to use                              |
|------------|------------------------------------------|
| `feat`     | New feature                              |
| `fix`      | Bug fix                                  |
| `refactor` | Code restructure without behaviour change|
| `docs`     | Documentation only                       |
| `test`     | Adding or updating tests                 |
| `chore`    | Build / CI / tooling changes             |

## Pull Request Checklist

- [ ] Tests pass (`cd backend && python -m pytest tests/ -v`)
- [ ] No broken asset references in HTML files
- [ ] New database changes include a migration file
- [ ] Documentation updated if applicable
- [ ] PR title follows commit message format above

## Reporting Issues

Please use GitHub Issues to report bugs or request features. Include:
- Steps to reproduce
- Expected vs actual behaviour
- Environment details (OS, Python version, browser)
