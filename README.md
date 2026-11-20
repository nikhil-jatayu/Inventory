# Inventory Management & Dispatch Planning

A single place to track item stock, purchase orders, dispatch plans, actual dispatches and customer
rejections. Built with FastAPI + PostgreSQL and Next.js.

**v1** — authentication/roles, Item Master, stock ledger and
status, purchase order management, the monthly dispatch calendar, stock vs schedule, actual dispatch
recording, financial-year/monthly/cumulative reporting with charts, quality rejections with issue
maintenance and Pareto analysis, and a home dashboard with KPIs, a dispatch-calendar summary and key
charts.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PostgreSQL, JWT + bcrypt
- **Frontend:** Next.js (App Router, TypeScript), Tailwind CSS, FullCalendar, Recharts
- **Structure:** routers → services → models, with Pydantic schemas for all I/O

## Project layout

```
Inventory/
├─ .env.example          # environment template
├─ backend/
│  ├─ app/
│  │  ├─ api/            # routers + auth dependencies
│  │  ├─ core/           # config, database, security, errors
│  │  ├─ models/         # SQLAlchemy models (all domain tables)
│  │  ├─ schemas/        # Pydantic request/response models
│  │  ├─ services/       # business logic and queries
│  │  ├─ main.py
│  │  └─ seed.py         # seed users
│  ├─ alembic/           # migrations
│  └─ requirements.txt
└─ frontend/
   ├─ src/app/           # login, dashboard, stock, items, purchase orders, planning, stock vs schedule, dispatches, rejections, users
   ├─ src/components/    # UI primitives and feature components
   └─ src/lib/           # API client, auth, types, helpers
```

## Setup

### 1. Environment

Create the database once (the app expects it to exist), then copy the env template:

```powershell
Copy-Item .env.example .env
```

Set at least:

```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/Inventory
SECRET_KEY=<long random string>
CORS_ORIGINS=http://localhost:3000
FY_START_MONTH=4
LEAD_TIME_NORMAL_DAYS=15
LEAD_TIME_URGENT_DAYS=10
LEAD_TIME_EMERGENCY_DAYS=4
```

The repository does not include a real `.env`; `.env.example` documents the variables. `SECRET_KEY`
signs JWTs — use a long random value in every environment.

### 2. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

macOS/Linux: `source .venv/bin/activate`.

- API: `http://localhost:8000/api`
- Swagger: `http://localhost:8000/api/docs`
- Health: `http://localhost:8000/api/health`

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. It calls `http://localhost:8000/api` by default. To override, create
`frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## Seeded accounts

`python -m app.seed` is idempotent and creates one account per role:

| Username | Password      | Role    |
| -------- | ------------- | ------- |
| admin    | `admin@123`   | ADMIN   |
| store    | `store@123`   | STORE   |
| quality  | `quality@123` | QUALITY |
| viewer   | `viewer@123`  | VIEWER  |

Change these passwords (Admin → Users → Edit) after first sign-in.

## Roles

- **ADMIN** — manages users and all data.
- **STORE** — item master, purchase orders, stock receipts/adjustments, dispatch plans and actual
  dispatches.
- **QUALITY** — records customer rejections and maintains the rejection-issue list.
- **VIEWER** — read-only access to dashboards.

Write permissions are enforced on the server for every write endpoint; the UI only hides controls.

## How stock works

- `stock_transactions` is an append-only ledger with signed quantities.
- **Available stock = SUM(quantity)** per item, computed in SQL.
- **Status:** `CRITICAL` when available < critical level, otherwise `BELOW_REORDER` when available <
  reorder level, otherwise `OK`. Levels must satisfy `critical_level <= reorder_level`; both
  thresholds are strict.
- Receipts and opening stock must be positive; adjustments are signed. An adjustment can never take
  available stock below zero.
- Actual dispatches post `DISPATCH` transactions automatically. Manual `DISPATCH` entries are
  rejected.
- Items are soft-deleted (`is_active=false`) and kept for history. Inactive items are hidden from
  stock status and cannot receive new stock entries.

## Purchase orders and dispatch planning

- A purchase order has a unique (case-insensitive) PO number, customer, unit number, PO date and one
  or more item lines. An item can appear only once per PO and must be active.
- **Line metrics:** `planned` = outstanding quantity on plans whose status is not `DONE`,
  `dispatched` = recorded dispatches, `balance = ordered − dispatched`, and `available to plan =
  balance − planned`.
- Line quantities cannot be reduced below planned + dispatched, and a line with planning or dispatch
  history cannot be removed.
- PO status is derived automatically: `COMPLETED` when all ordered quantity is dispatched, `PARTIAL`
  when some is dispatched, otherwise `OPEN`. `CANCELLED` is manual and only allowed when the PO has no
  dispatches and no outstanding plans. Cancelled POs are read-only.
- A dispatch plan stores a PO line, quantity, planned date and priority. Its quantity is capped at
  the line's available-to-plan balance; when editing, the plan's own outstanding quantity is added
  back and the quantity cannot fall below what has already been dispatched. A plan is `PLANNED`
  until any quantity is fulfilled, `PARTIAL` while partly fulfilled, and `DONE` once fully
  dispatched.
- **Lead-time warning:** a plan warns when `days_until < lead_time_days` for its priority (strict
  comparison). Defaults are Normal 15, Urgent 10 and Emergency 4 days, configurable through
  `LEAD_TIME_*_DAYS` in `.env`. Completed plans do not warn.
- The calendar month view fetches only the visible date range. Filtering by priority, status or text
  applies to the same range; warnings are listed beside the calendar.
- **Stock vs schedule** compares available stock with outstanding planned quantities for a period
  (default: the current calendar month). Only plans inside the period and not `DONE` count.
  `shortfall = max(planned − available, 0)`. Items are flagged as shortfall, critical, below reorder
  and needs replenishment (shortfall or available below reorder), with family/status filters and
  sorting.

## Actual dispatch and reports

- A dispatch records a PO line, dispatch date, quantity and optional remarks. It is rejected when the
  quantity exceeds the PO line balance or available stock, the PO is cancelled, or the item is
  inactive. Only Admin and Store can record dispatches.
- Recording a dispatch writes a negative `DISPATCH` stock-ledger entry (reference = PO number) and
  fulfils open plans for that line in planned-date order. Dispatch records are append-only; there is
  no delete endpoint.
- **Financial year:** April–March by default. `FY_START_MONTH` in `.env` changes the start month.
  `GET /api/reports/dispatch?fy=2025-26&family=...` returns 12 monthly buckets with planned,
  dispatched and cumulative quantities; financial-year totals; available FY options; total
  dispatched and planned for the selected FY; cumulative dispatched through the FY end; and the
  dispatch count. An invalid FY label returns `422`.
- **Actual Dispatch page:** FY and family filters, KPI cards, planned-vs-actual, cumulative and
  financial-year comparison charts, a monthly summary table, and a searchable/sortable dispatch
  record table. The record list is not date-limited by the selected FY.

## Quality rejections

- Only **Admin** and **Quality** can record rejections. A rejection stores the item, rejection date,
  quantity, an issue and optional remarks.
- **Rejections never change stock.** They record customer rejections of material already dispatched,
  so no stock-ledger entry is written. This rule lives in one service function
  (`apply_rejection_stock_effect`) as a documented no-op.
- The issue can be chosen from the maintained list or typed as a new name while recording. Names are
  trimmed, case-insensitively deduplicated, and reactivated automatically when a previously
  deactivated name is reused.
- Issues are maintained on the Quality Rejections page: add, rename or deactivate. Deactivation uses
  `DELETE /api/rejection-issues/{id}` (sets `is_active=false`); issues with history are never
  hard-deleted.
- **Rejection report:** `GET /api/reports/rejections?fy=2025-26&family=...` returns 12 monthly
  rejection-quantity buckets, the issue breakdown with share and cumulative share (Pareto), total
  quantity, record count, the top issue and available FY options. An invalid FY returns `422`.
- **Quality Rejections page:** FY and family filters; KPI cards; a monthly rejection-quantity chart;
  a Pareto chart of top issues; the issue-maintenance list; and a searchable, sortable, date-limited
  rejection record table.

## Home dashboard

- `/` and sign-in redirect to `/dashboard`, which is the landing page.
- Filters are independent: **month** (`YYYY-MM`) drives the KPI cards, calendar summary and shortfall;
  **financial year** drives the monthly charts and Pareto issues; **family** applies to all.
- **KPI cards:** critical items, items below reorder, total shortfall for the selected month
  (`planned − available` for outstanding plans), planned this month, dispatched this month and
  rejected this month.
- **Dispatch calendar summary:** a compact month grid showing planned quantity and plan count per day,
  colour-coded by the highest priority present, plus planned total, urgent days and emergency days.
- **Charts:** monthly planned vs dispatched vs rejected across the selected FY, and top rejection
  issues with cumulative share (Pareto).
- The endpoint is `GET /api/dashboard?month=&fy=&family=`. Invalid month or FY values return `422`.

## Useful commands

```powershell
# Apply new migrations
cd backend
python -m alembic upgrade head

# Create a migration after model changes
python -m alembic revision --autogenerate -m "describe change"

# Re-run seed (safe)
python -m app.seed
```
