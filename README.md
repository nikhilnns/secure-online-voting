# Secure Online Voting Management System

A secure, web-based election platform built with **Python Flask**, **SQLAlchemy (SQLite)**, **JWT** and a vanilla **HTML/CSS/JS** single-page frontend.
Course project for *Building Enterprise Applications (BCS703B)* – Dept. of Information Science & Engineering, BMS Institute of Technology & Management, 2026-27.

**Team:** Nimmala Nikhil Sai (1BY23IS138) · Nithin Kumar K (1BY23IS141) · Pawan B G (1BY23IS147) · Pratyush Kesari A (1BY23IS156)
**Guide:** Prof. Poornima G J, Assistant Professor, Dept. of ISE

## Key features

| Area | What it does |
|---|---|
| Authentication | Voter self-registration, PBKDF2/scrypt password hashing (Werkzeug), JWT (HS256, 60 min expiry), account lockout after 5 failed logins, per-IP rate limiting, generic login errors (no user enumeration) |
| Authorization | Role-based access (`admin`, `voter`); voters must be **approved** by an admin before they can vote |
| Election lifecycle | `draft → open → closed` (one-way). Candidates editable only in draft; at least 2 candidates to open |
| One person, one vote | Checked in code **and** enforced by a DB unique constraint `(election_id, user_id)` – safe against race conditions |
| Ballot secrecy | Ballots store **no user id and no timestamp**; participation is recorded separately from the choice |
| Tamper evidence | Every ballot is HMAC-SHA256 chained to the previous one. Admin "Verify integrity" recomputes the chain and cross-checks ballot count vs. participation records |
| Voter receipts | Voter gets a one-time receipt code (only its SHA-256 hash is stored) to confirm the ballot is in the ledger – the candidate is never revealed (prevents coercion / vote selling) |
| Results | Tally with percentages, tie detection and turnout; public only after closing (admin sees live tally) |
| Audit trail | Every security-relevant action (login, lockout, approvals, election changes, votes cast, integrity checks) logged with actor + IP |
| Web hardening | Strict Content-Security-Policy (no inline JS/CSS), X-Frame-Options DENY, nosniff, no-store on API, CORS allow-list, 64 KB body limit, HTML escaping in the UI |

## Project structure

```
secure-online-voting/
├── frontend/                    # UI (served by Flask)
│   ├── templates/index.html     # Single-page app shell
│   └── static/{css,js}/         # Styles and client logic (no inline scripts)
├── backend/                     # Server application
│   ├── app.py                   # Application factory, error handlers
│   ├── config.py                # Environment-driven configuration
│   ├── extensions.py            # SQLAlchemy instance
│   ├── routes/                  # API route definitions (Flask blueprints)
│   ├── controllers/             # Business logic (auth, elections, voting, admin)
│   ├── models/                  # ORM models: User, Election, Candidate, VoteRecord, Ballot, AuditLog
│   ├── middleware/              # JWT auth/RBAC, validation, security headers, CORS, rate limiting
│   └── utils/                   # Hash-chain crypto, audit helper, error type
├── tests/                       # PyTest unit + API tests (54 tests)
├── docs/                        # Screenshots and static-analysis / test reports
├── scripts/quality.sh|.bat      # Run all quality gates
├── app.py                       # Entry point (python app.py)
├── seed_demo.py                 # Demo data
├── Dockerfile, docker-compose.yml
└── requirements.txt, requirements-dev.txt
```

## Run locally

Requires **Python 3.10+**.

```bash
python -m venv venv
# Windows: venv\Scripts\activate      Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python seed_demo.py        # optional: demo voters + elections
python app.py              # http://127.0.0.1:5000
```

Default logins (change via env vars `ADMIN_EMAIL` / `ADMIN_PASSWORD` before any real use):

| Role | Email | Password |
|---|---|---|
| Admin | admin@vote.local | Admin@1234 |
| Voter (demo) | ananya@college.edu, rahul@college.edu, sneha@college.edu, karthik@college.edu, meera@college.edu | Voter@1234 |
| Pending voter (demo) | arjun@college.edu | Voter@1234 |

### Docker

```bash
docker compose up --build    # http://localhost:5000
```

## Tests and static analysis

```bash
pip install -r requirements-dev.txt
python -m pytest --cov=backend          # 54 passed, 92% coverage
pylint backend app.py seed_demo.py      # 10.00/10
flake8 backend tests app.py seed_demo.py
bandit -r backend app.py seed_demo.py   # No issues identified
# or everything at once:
./scripts/quality.sh        (Windows: scripts\quality.bat)
```

Saved outputs are in `docs/reports/`.

## REST API

All endpoints except register/login/health need `Authorization: Bearer <token>`.

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | public | Register voter (pending) |
| POST | `/api/auth/login` | public | Get JWT |
| GET | `/api/auth/me` | any | Current profile |
| GET | `/api/elections` | any | List elections (voters: no drafts, with `has_voted`) |
| GET | `/api/elections/<id>` | any | Election + candidates |
| POST | `/api/elections` | admin | Create draft election |
| DELETE | `/api/elections/<id>` | admin | Delete draft election |
| POST | `/api/elections/<id>/candidates` | admin | Add candidate |
| DELETE | `/api/elections/<id>/candidates/<cid>` | admin | Remove candidate |
| PATCH | `/api/elections/<id>/status` | admin | `{"status": "open" \| "closed"}` |
| GET | `/api/elections/<id>/results` | any | Results (voters: after close) |
| POST | `/api/votes` | voter | `{"election_id", "candidate_id"}` → receipt |
| POST | `/api/votes/verify` | any | `{"election_id", "receipt"}` |
| GET | `/api/admin/stats` | admin | Dashboard numbers |
| GET | `/api/admin/voters?status=` | admin | List voters |
| PATCH | `/api/admin/voters/<id>` | admin | `{"status": "approved" \| "rejected"}` |
| GET | `/api/admin/elections/<id>/verify` | admin | Ledger integrity report |
| GET | `/api/admin/audit-logs?limit=` | admin | Audit trail |
| GET | `/api/health` | public | Health check |

## Repository

https://github.com/Pratyushkesari/secure-online-voting

## Branching practice

* `main` – stable, release-ready code
* `dev` – integration branch
* `feature/*` – one branch per feature (e.g. `feature/ballot-ledger`), merged into `dev` via pull request, then `dev` → `main`

## Known limitations / future work

* SQLite is used for simplicity; switch `DATABASE_URL` to PostgreSQL/MySQL for production.
* The in-memory rate limiter is per-process; use Redis for multi-instance deployments.
* Ballot order in the chain could in theory be correlated with participation order by someone with full DB + log access; batching/shuffling ballots before insertion would close this.
* Add e-mail/OTP verification and HTTPS termination (reverse proxy) for real deployments.
