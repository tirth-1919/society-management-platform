# COMPLETE FILE ERROR AUDIT
Scope: source and test assets present in this repository, with safe verification against the isolated pytest application. `[PASS]` means inspected and covered by available checks; `[POSSIBLE RISK]` means environment- or scenario-dependent and not a confirmed error; `[NOT TESTED]` means it requires external services, authenticated domain fixtures, or state-changing actions.

## Audit totals
- Files inspected: 364 repository files excluding virtual-environment files
- Python files: 123
- Route files: 15
- Templates: 81
- Static files: 11
- Test files: 43
- Confirmed runtime errors: 0
- Confirmed HTTP 500 errors: 0
- Possible 500 risks: 8 review items
## Application Files
| File | 500 | 400 | 401 | 403 | 404 | 405 | DB | Template | Production | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `app/__init__.py` | [PASS] handlers/factory | [PASS] | [PASS] | [PASS] | [PASS] | [NOT TESTED] | [POSSIBLE RISK] init/schema patch | [PASS] | [POSSIBLE RISK] env/storage | [PASS] |
| `app/config.py` | [POSSIBLE RISK] env | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [POSSIBLE RISK] PostgreSQL env | [NOT TESTED] | [POSSIBLE RISK] secrets/storage | [PASS] |
| `run.py` | [PASS] startup | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [POSSIBLE RISK] runtime DB | [NOT TESTED] | [POSSIBLE RISK] Gunicorn/env | [PASS] |
| `run_user.py` | [PASS] startup | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [POSSIBLE RISK] seed/runtime DB | [NOT TESTED] | [POSSIBLE RISK] filesystem/env | [PASS] |
| `run_admin.py` | [PASS] startup | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [NOT TESTED] | [POSSIBLE RISK] runtime DB | [NOT TESTED] | [POSSIBLE RISK] cookie/env | [PASS] |

## Routes
| File | Route coverage | Methods | Possible error areas | Tested | Status |
|---|---|---|---|---|---|
| `app/routes/auth.py` | login, logout, register, registration status, OTP | GET/POST | session, validation, DB, 400/401/404/500 | safe GET + existing auth tests | PASS |
| `app/routes/main.py` | index, dashboard, lookup APIs, QR | GET/POST | auth, query parsing, QR/file response | safe GET | PASS |
| `app/routes/admin.py` | admin dashboard, residents, registrations, actions, reports | GET/POST | RBAC, tenant scope, missing relationships | safe GET + existing admin tests | PASS |
| `app/routes/resident.py` | resident pages, bills, receipts, support, notifications | GET/POST | session, missing records, PDFs | safe GET + existing portal tests | PASS |
| `app/routes/payments.py` | bills, payments, receipts, refunds, webhooks | GET/POST | provider/DB/PDF/external failures | safe GET only | PASS / mutation paths NOT TESTED |
| `app/routes/api.py` | JSON residents, bills, search, health, automation | GET/POST | JSON/query/auth/DB | safe GET | PASS |
| `app/routes/accounting.py` | ledgers, vouchers, resident ledger | GET/POST | DB joins, tenant scope, exports | safe GET | PASS |
| `app/routes/complaints.py` | complaint list/detail/create/actions | GET/POST | missing records, auth, form validation | safe GET | PASS |
| `app/routes/documents.py` | document vault/download | GET/POST | file missing/permission, auth | safe GET | PASS |
| `app/routes/facilities.py` | facility listing/booking | GET/POST | form/DB/auth | safe GET | PASS |
| `app/routes/operations.py` | assets, inventory, parking, vendors | GET/POST | empty DB/auth | safe GET | PASS |
| `app/routes/reports.py` | reports and exports | GET | query/export/auth | safe GET | PASS |
| `app/routes/system_health.py` | health, readiness, backups | GET/POST | DB/filesystem | safe GET | PASS |
| `app/routes/visitors.py` | visitor pages/actions | GET/POST | auth/form/DB | safe GET | PASS |

## Services
All Python files under `app/services/` were inspected for database, relationship, filesystem, PDF, external-provider, and exception-sensitive operations. Existing non-browser test suite and route tests passed. Payment provider calls, webhooks, destructive actions, and external services remain possible-risk/not-tested scenarios rather than confirmed failures.

| Service group | Possible error | Tested | Status |
|---|---|---|---|
| Billing/maintenance services | calculation/DB edge cases | existing tests | PASS |
| Payment/provider/reconciliation services | provider/network/transaction failure | unit/domain tests; external provider not live | POSSIBLE RISK |
| Notification/automation services | missing user/DB/job context | existing tests | PASS |
| Receipt/PDF/document services | missing path/permission/font/file | invalid route + existing tests | POSSIBLE RISK |
| Backup/report/search/health services | filesystem/DB/environment | existing tests + safe GET | PASS / environment risk |

## Templates
| Template set | Possible Jinja error | Missing variable | `url_for` error | Static error | Status |
|---|---|---|---|---|---|
| 81 templates under `app/templates/` | compile check PASS | authenticated contexts not exhaustive | static endpoint reference check PASS | static assets exist | PASS / authenticated context NOT EXHAUSTIVE |

## Static Files
| File set | Type | Possible error | Status |
|---|---|---|---|
| 11 files under `app/static/` | CSS/JS/images | browser/provider-specific behavior | browser tests passed; files exist | PASS |

## Configuration
| File | Configuration | Possible problem | Status |
|---|---|---|---|
| `requirements.txt` | dependencies | missing deployment dependency | installed/tested locally | PASS |
| `pytest.ini` | test discovery/warnings | suite duration | inspected | PASS |
| `app/config.py` | SQLite/PostgreSQL, sessions, CSRF, secrets, storage | deployment env/filesystem | local testing config verified | POSSIBLE RISK |
| `run.py`, `run_user.py`, `run_admin.py` | startup | runtime DB/Gunicorn/env | factory startup PASS | PASS |
| Render/Procfile configuration | deployment | no relevant file discovered | NOT TESTED |

## Tests
| Test File group | Result | Status |
|---|---|---|
| Existing non-browser tests | 189 passed in bounded groups | PASS |
| Existing browser tests | 47 passed in bounded groups | PASS |
| `test_route_smoke.py` | PASS, 0 HTTP 500 | PASS |
| `test_dynamic_routes.py` | PASS | PASS |
| `test_template_routes.py` | PASS | PASS |
| `test_500_edge_cases.py` | PASS | PASS |
| `test_complete_error_audit.py` | 3 passed; safe GET result 0 HTTP 500 | PASS |

## HTTP results from complete safe GET audit
- 200: 10
- 3xx: 34 (all 302)
- 400: 0
- 401: 7
- 403: 55
- 404: 8
- 405: 0
- 500: 0
- Other: 0
## Confirmed errors and possible risks
- Confirmed errors: none found by static inspection and available tests.
- Possible risks: external payment/provider failures; production PostgreSQL/migration compatibility; Render filesystem permissions; authenticated valid-record combinations not exhaustively generated; state-changing POST/PUT/PATCH/DELETE paths intentionally not executed by this read-only audit.
- No application source, business logic, models, migrations, or production data were changed.
