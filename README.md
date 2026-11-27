# Inventory Management & Dispatch Planning

Client-aligned inventory, purchase, dispatch, sales and operational reporting application based on the DA SVARN STOCK DASHBOARD workbook. FastAPI, SQLAlchemy, Alembic and PostgreSQL provide the backend; Next.js, React, TypeScript, Tailwind CSS and Recharts provide the frontend. Quantities are pieces, not monetary revenue or tax invoice amounts.

## Workflows and business rules

| Section | Behaviour |
|---|---|
| Item Master | Item and project identify a distinct item; family, model, inventory and stock thresholds follow the workbook. |
| Units | Four initial locations, with additional active locations selectable in forms. |
| Purchase Orders | Eight-digit text PO numbers preserve leading zeros. Multi-item entries and multiple locations; bookkeeping only. |
| Purchase Planning | Independent dated plans, batch entry, calculated categories and a continuous Gantt. |
| Purchases | Accepted receipts link to purchase plans, reduce their outstanding quantities and increase stock once. |
| Purchase Rejections | Alphanumeric RGP references; cancel outstanding plan quantities without changing stock. |
| Dispatch Planning | Item, unit, quantity, date range and category; no PO required. |
| Actual Dispatch | Partial or full fulfilment of a plan; stock and outstanding quantities checked. Multiple lines share an automatic invoice; optional PO reference. |
| Sales | Gross dispatched quantity, linked unit rejection quantity and net quantity; no second stock deduction. |
| Unit Rejections | Linked to actual dispatched lines; limited to their remaining rejectable quantities. No automatic return to usable stock or reopening of dispatch plans. |
| Stock | Signed stock ledger is the source of available inventory. Manual stock transactions remain supported for authorized users. |
| Dashboard and Stock vs Schedule | Monthly planned dispatch, current stock vs outstanding planned demand, monthly net sales and shortages. |
| Reports | Filtered previews with matching Excel and PDF exports. |
| Users | Role-controlled access and management. |

Purchase outstanding = planned − received − cancelled. Dispatch outstanding = planned − dispatched. Net sales = gross dispatched − linked customer rejections. A rejection restates the original invoice month's net sales; the rejection register uses the rejection's own date. Legacy unlinked records are retained, not automatically matched or deducted from individual plan/invoice balances. The stock ledger is shared across units; unit filters are not supported for shared-stock and purchase reports.

Planning categories use calendar-day difference between start and end dates. With the default thresholds, more than 15 days is Normal, 8–15 is Urgent, and 0–7 is Emergency. Durations of 0–4 days have a separate short-duration warning where applicable. Overdue means an unfinished plan has passed its end date. The shared Gantt spans 365 days (182 days on either side of today), supports horizontal scrolling and a Today recenter button, and shows cross-month bars and actual dispatch markers where applicable. Timeline navigation is independent of monthly KPI periods. Plan report totals use plan start date; actual activity uses transaction date.

## Reports

- Management Summary
- Stock vs Dispatch Plan
- Dispatch Performance
- Sales Reconciliation
- Purchase Plan vs Actual Purchase
- Unit Rejections
- Purchase Rejections
- Inventory Stock Ledger

Report filters include period, project, family, item and unit where applicable. Preview, Excel and PDF use the same report calculation. Reports cover quantities only. The purchase register currently loads at most the latest 500 records; the report builder does not use that cap.

## Initial master data

| Item | Project | Family | Model | Opening | Reorder | Critical |
|---|---|---|---|---:|---:|---:|
| 8U | Indus | FCT | — | 1000 | 500 | 250 |
| 12U Old | Indus | FCT | — | 0 | 0 | 0 |
| 12U New | Indus | FCT | — | 0 | 0 | 0 |
| VRLA | Indus | FCT | — | 0 | 0 | 0 |
| 23U | Indus | FCT | — | 0 | 0 | 0 |
| 25U | Indus | FCT | — | 0 | 0 | 0 |
| 35U | Indus | FCT | 35UFCT221CX | 0 | 0 | 0 |
| LED 2.5W | Indus | LED | — | 0 | 0 | 0 |
| FCTS6D | RELIANCE | FCTS | — | 0 | 0 | 0 |
| FCTS6D | AIRTEL | FCTS | — | 0 | 0 | 0 |

Blank numeric workbook fields are initialized to zero; confirm opening balances and thresholds with the client before live use. The four initial locations are Unit-1 through Unit-4. Master records can be extended through the application. Reorder and critical values are configured thresholds, not changing inventory balances; current implementation flags stock strictly below the corresponding thresholds.

## Local setup (Windows PowerShell)

Use Python 3.14, Node.js and npm compatible with the checked-in lockfile, Git, and PostgreSQL 17 (Docker is optional). The verified local setup used Python 3.14 and Node 24. Use the repository root as the starting directory for the following commands. Do not overwrite an existing `.env` or create another container if the database already exists.

For a new local development database only, generate private credentials and start PostgreSQL:

```powershell
$dbPassword = python -c "import secrets; print(secrets.token_hex(24))"
$jwtSecret = python -c "import secrets; print(secrets.token_hex(48))"
docker volume create inventory-postgres-data
docker run --name inventory-postgres `
  -e POSTGRES_USER=inventory_admin `
  -e "POSTGRES_PASSWORD=$dbPassword" `
  -e POSTGRES_DB=inventory `
  -p 127.0.0.1:5437:5432 `
  -v inventory-postgres-data:/var/lib/postgresql/data `
  --restart unless-stopped -d postgres:17
```

Wait for PostgreSQL readiness (`docker exec inventory-postgres pg_isready -U inventory_admin -d inventory`). If reusing an existing container, use its existing credentials and `docker start inventory-postgres` if necessary.

For a fresh environment file only:

```powershell
if (Test-Path .env) { throw 'Existing .env: configure it manually instead.' }
@"
DATABASE_URL=postgresql+psycopg://inventory_admin:${dbPassword}@127.0.0.1:5437/inventory
SECRET_KEY=$jwtSecret
CORS_ORIGINS=http://localhost:3000
FY_START_MONTH=4
LEAD_TIME_NORMAL_DAYS=15
LEAD_TIME_URGENT_DAYS=7
LEAD_TIME_EMERGENCY_DAYS=4
"@ | Set-Content -Encoding ascii .env
```

Never commit `.env`, actual passwords, JWT secrets, database dumps or the demonstration manifest. If using another database, set its URL explicitly and verify the target before migrations or seeding.

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -m alembic upgrade head
python -m alembic check
# Only for a fresh local development/demo database:
python -m app.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use the existing virtual environment instead of recreating it when already installed. If Windows application control blocks SQLAlchemy's optional C extensions, set `$env:DISABLE_SQLALCHEMY_CEXT_RUNTIME = "1"` in the backend terminal before running Python. Back up existing databases before any migration. The expected migration head is `c4f7a91d2e60`. Its downgrade cannot reconstruct old category values; retain the pre-migration backup. Do not run the master seed against an operational database without approval: it can update the predefined client item details and thresholds. The optional `--deactivate-non-client-items` flag also deactivates other active items without deleting history.

API base: `http://localhost:8000/api`. Swagger: `http://localhost:8000/api/docs`. Health: `http://localhost:8000/api/health`.

### Frontend

Open a second terminal at the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. The API URL can be overridden in `frontend/.env.local` using `NEXT_PUBLIC_API_URL=http://localhost:8000/api`. For a built application, run `npm run build` then `npm run start` instead of `npm run dev`.

### Roles and starter accounts

The local seed creates admin, store, quality and viewer accounts if missing. Their development-only starter credentials are defined in `backend/app/seed.py`. Admin manages users; Admin and Store manage items, units, POs, purchase workflows, stock and dispatch workflows; Admin and Quality record customer rejections. Authenticated users have access to reports and permitted read views. Replace all default credentials before shared access. The starter seed is not a secure production provisioning system.

## Testing and release checks

From `backend` with the virtual environment active:

```powershell
python -m compileall -q app alembic checks
python -m unittest discover -s checks -v
python -m alembic current
python -m alembic check
python -c "from app.main import app; print(len(app.openapi()['paths']))"
```

The 19 service regression tests use isolated SQLite databases. They do not replace PostgreSQL migration, concurrency or direct HTTP authorization testing. The current API exposes 44 paths. Run migrations and interactive write tests on a dedicated development database, not a client database.

From `frontend`:

```powershell
npx next typegen
npx tsc --noEmit
npm run lint
npm run build
```

Functional verification: create a distinct test item and additional unit; check leading-zero POs; create purchase plans, partial receipts and cancellations; dispatch against plans with and without PO references; verify invoices, rejections, stock and net sales; reconcile previews and exported reports; check failed batch rollback and role permissions. Use an isolated database and verify `SELECT current_database()` before starting the backend. A PowerShell `$env:DATABASE_URL` override is session-specific; reapply it whenever starting in a new terminal.

## Local demonstration data

`python -m app.demo_seed status`, `seed` and `clear` are a local-only utility for the `inventory` database on localhost port 5437. It requires the expected ten-item master, opening ledger baseline, active admin and initial units. Never use this utility for live operational data. Back up the database and `.inventory-demo-state.json` together. Clear refuses if recorded snapshots differ, requires typing `CLEAR DEMO`, and removes only the recorded sample rows while preserving the verified baseline. Do not edit the manifest to bypass this guard. Clear the old sample dataset before the duration-category migration if its hashes still match, then regenerate when ready for the demo. If the manifest is missing or changed, stop and reconcile with a verified backup. Do not run the demo utility on `inventory_test`. The seed is not automatically run on startup.

## Production handover boundaries

This release is intended for local functional verification and client demonstration. Before network-facing production use, confirm client master balances and thresholds, provision unique credentials securely, review authentication/session handling and login rate limiting, configure HTTPS, restrict CORS and database access, verify backups/restores, and run PostgreSQL concurrency and direct API permission tests. Historical unlinked transactions require an explicit reconciliation decision, not automatic guessed links. Confirm manual stock adjustments and Store unit-management permissions with the business owner.

## Structure

- `backend/app/api`: API routers and role dependencies
- `backend/app/core`: configuration, database and security
- `backend/app/models`, `schemas`, `services`: persistence, validation and business rules
- `backend/alembic/versions`: migration history
- `backend/checks`: isolated regression tests
- `frontend/src/app`, `components`, `lib`: pages, forms, timeline, reports and client utilities
