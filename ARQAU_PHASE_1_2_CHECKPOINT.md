# ARQAU Phase 1.2 Development Checkpoint

> Status: **Phase 1.2 — IN PROGRESS**
> Date: 2026-09-12
> Branch: *(see git status below)*
> Git state: **Uncommitted changes present** — do **NOT** commit or reset.

---

## 1. Git State

Run these commands to refresh state before continuing:

```powershell
git -C C:\Users\brawl\Desktop\arqau-landing-page\arqau status
git -C C:\Users\brawl\Desktop\arqau-landing-page\arqau branch --show-current
git -C C:\Users\brawl\Desktop\arqau-landing-page\arqau log --oneline -5
git -C C:\Users\brawl\Desktop\arqau-landing-page\arqau diff --stat
```

**Last recorded git state at checkpoint creation:**

| Item | Status |
|---|---|
| Phase 1.1 | Committed as baseline (assumed — verify with `git log`) |
| Phase 1.2 | All changes **uncommitted** (new files + modified files) |
| arqau.db | Git-ignored (`*.db`); regenerated as legacy DB with `alembic_version = 20260911_0001`, Phase 1.2 tables dropped. Re-regenerate before running migration tests if corrupted by test teardown. |

---

## 2. Phase 1.1 Baseline (Already Complete)

Phase 1.1 was completed and validated before Phase 1.2 work began. Foundation in place:

- Environment-aware configuration (`APP_ENV`, `SECRET_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`)
- SQLite for development/testing; PostgreSQL for production
- Centralized async SQLAlchemy database layer (`app/core/database.py`)
- Alembic foundation (`alembic.ini`, `env.py`, `20260911_0001_initial_schema.py`)
- Guarded baseline migration (0001)
- Production `create_all` protection (lifespan skips `create_all` when `environment == "production"`)
- Legacy SQLite preservation (`arqau.db` with application data)
- Existing API compatibility (auth, onboarding, EWA, finance, transactions)
- Existing tests: `test_api.py`, `test_config.py`, `test_database.py`, `test_alembic.py`

**Do NOT redo Phase 1.1.**

---

## 3. Phase 1.2 Original Goal

New domain foundation:

```
User → Employee → Employment → Employer
Employment → SalaryProfile
```

Important architectural decisions (MUST be preserved):

- `User.id` must remain unchanged
- Employee should NOT duplicate `employer_id` — employer ownership belongs to **Employment**
- SalaryProfile belongs to Employment
- Legacy `monthly_income_range` must NEVER be converted into guessed numeric salary
- Legacy tables must remain intact
- No EWA redesign
- No auth/RBAC redesign
- No frontend redesign
- All schema changes additive

---

## 4. What Has Actually Been Implemented

### 4.1 Models (`backend/app/models.py`)

| Entity | `id` column | UUID default | Status |
|---|---|---|---|
| Employer | `Column(String, primary_key=True)` | `default=lambda: str(uuid4())` | ✅ Implemented, tests pass |
| Employee | `Column(String, primary_key=True)` | `default=lambda: str(uuid4())` | ✅ Implemented, tests pass |
| Employment | `Column(String, primary_key=True)` | `default=lambda: str(uuid4())` | ✅ Implemented, tests pass |
| SalaryProfile | `Column(String, primary_key=True)` | `default=lambda: str(uuid4())` | ✅ Implemented, tests pass |
| User | `Column(String, primary_key=True)` | unchanged | ✅ Unchanged |

**Key issue to verify:** SQLAlchemy `Column(default=...)` fires at INSERT time (flush), not at Python object construction time. Tests that construct dependent objects (e.g., `Employment(employee_id=employee.id)`) before the parent is flushed will get `None` for the FK. Fix: add `await session.flush()` after adding parent objects.

### 4.2 Schemas

**`backend/app/schemas/employee.py`**
- `EmployeeCreate`: user_id, external_employee_id, display_name, status — ✅ Present
- `EmployeeRead`: Changed `created_at: str` → `created_at: datetime`, `updated_at: Optional[str]` → `Optional[datetime]` — ✅ Fixed (Pydantic v2 rejects datetime for str fields with `from_attributes=True`)
- `EmployeeUpdate`: ✅ Present

**`backend/app/schemas/employer.py`**
- `EmployerCreate`: legal_name (min_length=1), display_name, registration_number, country — ✅ Present
- `EmployerRead`: `created_at: datetime`, `updated_at: Optional[datetime]` — ✅ Fixed
- `EmployerUpdate`: legal_name validator — ✅ Present

**`backend/app/schemas/employment.py`**
- `EmploymentCreate`: employee_id, employer_id, employment_type, status, start_date, end_date, eligible_from, eligible_to + `field_validator("end_date")` + `field_validator("eligible_to")` — ✅ Present
- `EmploymentRead`: `created_at: datetime` — ✅ Fixed
- `EmploymentUpdate`: ✅ Present

**`backend/app/schemas/salary.py`**
- `SalaryProfileCreate`: employment_id, currency (min_length=3), `monthly_salary_amount_minor` (gt=0), pay_schedule (Literal), payday_day (ge=1, le=31), effective_from (datetime), effective_to + `field_validator("effective_to")` — ✅ Present
- `SalaryProfileRead`: `created_at: datetime` — ✅ Fixed
- `SalaryProfileUpdate`: ✅ Present

### 4.3 Services

**`backend/app/services/employee_service.py`** — Complete
- `async create_employee(db, data)`: Checks User exists (ValueError if not), checks duplicate Employee by user_id (ValueError), catches IntegrityError, calls commit/refresh with await.
- `async get_employee_by_id(db, id)`: ✅
- `async get_employee_by_user_id(db, user_id)`: ✅

**`backend/app/services/employer_service.py`** — Complete
- `async create_employer(db, data)`: ✅
- `async get_employer_by_id(db, id)`: ✅

**`backend/app/services/employment_service.py`** — Complete
- `async create_employment(db, data)`: Checks Employer exists and Employee exists.
- `async get_employment_by_id(db, id)`: ✅

**`backend/app/services/salary_service.py`** — Complete
- `async create_salary_profile(db, data)`: Checks duplicate by employment_id.
- `async get_salary_profile_by_id(db, id)`: ✅
- `async get_active_salary_profile_by_employment(db, id)`: Filters by status="active". ✅

**Service naming fix:** Route handler functions and imported service functions had the same name (e.g., `create_employee`). Fixed by aliasing imports: `from app.services.employee_service import create_employee as create_employee_service`. Same for employers, employments, and salary services.

### 4.4 API Routes

**`backend/app/api/v1/employees.py`** — Complete
- POST `/employees/`: Calls `await create_employee_service(db, data)`, catches ValueError → 400.
- GET `/employees/{id}`: Calls `await get_employee_by_id(db, id)`.

**`backend/app/api/v1/employers.py`** — Complete
- POST `/employers/`: `await create_employer_service(db, data)`.
- GET `/employers/{id}`: `await get_employer_by_id(db, id)`.

**`backend/app/api/v1/employments.py`** — Complete
- POST `/employments/`: `await create_employment_service(db, data)`.
- GET `/employments/{id}`: `await get_employment_by_id(db, id)`.

**`backend/app/api/v1/salary.py`** — Complete (rewritten)
- POST `/salary-profiles/`: `await create_salary_profile_service(db, data)`.
- GET `/salary-profiles/{id}`: `await get_salary_profile_by_id(db, id)`.
- PUT `/salary-profiles/{id}`: Fixed from sync `db.commit()`/`db.refresh()` to `await db.commit()`/`await db.refresh(profile)`.
- GET `/salary-profiles/employment/{employment_id}`: `await get_active_salary_profile_by_employment(db, employment_id)`.

### 4.5 Alembic Migration

**`backend/alembic/versions/20260911_0002_employer_employee_employment_salary.py`** — Modified

- `_create_new_tables()`: ✅ Creates employers, employees, employments, salary_profiles with proper FK constraints, CheckConstraints, and indexes.
- `upgrade()`: Smart detection of existing tables (handles legacy databases without alembic_version, partial databases, fresh databases).
- `_drop_new_tables()`: **FIXED** — Previously did NOT drop the `employments` table. Now includes `op.drop_table("employments")` between `salary_profiles` and `employees` drops (correct FK ordering: salary_profiles → employments → employees → employers).
- `downgrade()`: Drops Phase 1.2 tables when `version in ("20260911_0002", "20260911_0001")` and all new tables exist.

### 4.6 Model Relationships

All relationships defined in models:
- `User.employee` (uselist=False) ↔ `Employee.user`
- `User.employments` (uselist=True, secondary through Employee) — verify actual definition
- `Employee.employments` (uselist=True) ↔ `Employment.employee`
- `Employer.employments` (uselist=True) ↔ `Employment.employer`
- `Employment.salary_profile` (uselist=False) ↔ `SalaryProfile.employment` (uselist=False, unique constraint on employment_id)

### 4.7 ID Generation — Current Status

- Python-side UUID via `default=lambda: str(uuid4())` on String primary keys
- **Limitation confirmed:** Default fires at INSERT time (flush), NOT at Python construction
- Tests must call `await session.flush()` after adding parent objects before using their `.id` as FK values in dependent objects

### 4.8 arqau.db State

- **Regenerated** as proper legacy database:
  - Phase 1.2 tables (employers, employees, employments, salary_profiles) dropped
  - `alembic_version` table created with `version_num = "20260911_0001"`
  - All legacy application data preserved (users: 4, onboarding: 1, transactions: 4, budgets: 2, goals: 3, earned_wages: 3, wage_access_requests: 4)
- **WARNING:** `arqau.db` is git-ignored. Tests that run ASGI lifespan with non-production settings may call `Base.metadata.create_all` which re-creates Phase 1.2 tables on `arqau.db`. Re-run `fix_db2.py` before migration tests if needed.

---

## 5. Current Test / Error State

### FIXED (verified passing)

| Test | File | Status |
|---|---|---|
| test_employer_can_be_created | test_phase12_models.py | ✅ PASS |
| test_employee_can_link_to_existing_user | test_phase12_models.py | ✅ PASS |
| test_duplicate_employee_for_same_user_is_rejected | test_phase12_models.py | ✅ PASS |
| test_employment_links_employee_to_employer | test_phase12_models.py | ✅ PASS |
| test_salary_profile_links_to_employment | test_phase12_models.py | ✅ PASS |
| test_monthly_salary_amount_minor_must_be_positive | test_phase12_models.py | ✅ PASS |
| test_invalid_employment_dates_rejected | test_phase12_models.py | ✅ PASS |
| test_invalid_salary_effective_dates_rejected | test_phase12_models.py | ✅ PASS |
| test_inactive_historical_employment_is_representable | test_phase12_models.py | ✅ PASS |
| test_active_salary_profile_retrieval_works | test_phase12_models.py | ✅ PASS |
| test_sqlite_startup_and_foreign_keys | test_phase12_database.py | ✅ PASS |
| test_phase12_model_metadata_compiles_for_postgresql | test_phase12_database.py | ✅ PASS |
| test_phase12_model_crud_and_relationships | test_phase12_database.py | ✅ PASS |
| test_production_lifespan_does_not_create_schema | test_phase12_database.py | ✅ PASS |
| test_legacy_auth_onboarding_ewa_finance_and_requests_unchanged | test_phase12_api.py | ✅ PASS |
| test_employer_endpoints_work | test_phase12_api.py | ✅ PASS |
| test_employee_duplicate_is_rejected | test_phase12_api.py | ✅ PASS |
| test_employee_nonexistent_user_returns_controlled_error | test_phase12_api.py | ✅ PASS (new test) |
| test_employment_and_salary_lifecycle | test_phase12_api.py | ✅ PASS |
| test_salary_safety_onboarding_does_not_create_salary_profile | test_phase12_api.py | ✅ PASS |
| test_fresh_sqlite_upgrade_creates_phase12_tables | test_phase12_migration.py | ✅ PASS |
| test_partial_legacy_database_is_rejected | test_phase12_migration.py | ✅ PASS |
| test_existing_models_compile_for_postgresql | test_alembic.py | ✅ PASS |

### Migration Tests — Intermittent Failure

**Root cause:** When all tests run together, prior test teardown calls `configure_database(original_url)` which sets the module-level SQLAlchemy engine to `arqau.db`. If `httpx.ASGITransport` runs the app lifespan afterward, it calls `Base.metadata.create_all` on the engine — which may create Phase 1.2 tables on `arqau.db`. This corrupts `arqau.db` and breaks migration tests that copy it.

| Test | Status when run alone | Status when run with all tests |
|---|---|---|
| test_downgrade_removes_only_phase12_tables | ✅ PASS | ❌ FAIL (table employers already exists) |
| test_legacy_sqlite_copy_upgrades_without_changing_legacy_data | ✅ PASS | ❌ FAIL (table employers already exists) |
| test_upgrade_after_downgrade_works_again | ✅ PASS | ❌ FAIL (table employers already exists) |
| test_empty_database_upgrade_creates_schema | ✅ PASS | ✅ PASS |
| test_legacy_database_is_stamped_without_data_changes | ✅ PASS | ❌ FAIL (table employers already exists) |

**Fix requirement:** Ensure `arqau.db` does not get Phase 1.2 tables re-created by test lifespan. Either:
- Re-run `fix_db2.py` before running migration tests, OR
- Make tests that call `configure_database(original_url)` also drop Phase 1.2 tables, OR
- Prevent ASGI lifespan `create_all` from running on `arqau.db` during test teardown

### IN PROGRESS

- Async relationship loading in model tests — tests currently use `selectinload` for collections, `expire_on_commit=False` for scalars. May need additional eager loading in future tests.

### UNRESOLVED

- **arqau.db corruption when running full suite:** The `arqau.db` file gets Phase 1.2 tables re-created when the full test suite runs (due to ASGI lifespan `create_all` on teardown-configured engine). This causes migration tests to fail with "table employers already exists".

### NOT VERIFIED AFTER LATEST CHANGES

- Full backend test suite (all tests in one run)
- Python compile (`python -m compileall`)
- `git diff --check`
- `alembic history`, `alembic heads`, `alembic check`
- Backend startup
- `/health` endpoint
- PostgreSQL DDL compilation (no live PostgreSQL)
- Frontend production build

---

## 6. Phase 1.2 422 Root Cause (Confirmed & Fixed)

**Root cause:** The `_token()` helper in `test_phase12_api.py` registered a user with email `phase12@example.com` but attempted login with email `phase12@example.test`. The `phase12@example.test` TLD is a reserved/testing TLD (RFC 2606) and `EmailStr` (via `email-validator`) rejects it, returning HTTP 422.

**Fix:** Login now uses the same `phase12@example.com` as registration.

---

## 7. Last Successful Test Results

```
Command: python -m unittest tests.test_phase12_models tests.test_phase12_database -v
Result: OK (14 tests, 0 failures, 0 errors)

Command: python -m unittest tests.test_phase12_api -v
Result: OK (6 tests, 0 failures, 0 errors)

Command: python -m unittest tests.test_phase12_migration tests.test_alembic -v (ALONE, after fix_db2.py)
Result: OK (9 tests, 0 failures, 0 errors)
```

**NOT VERIFIED AFTER LATEST CHANGES:** Full combined test suite (`python -m unittest discover -s tests`) due to `arqau.db` corruption issue.

---

## 8. Next Exact Actions (Continuation Checklist)

1. **Inspect this checkpoint + git diff** — understand current state
2. **Fix `arqau.db` corruption issue** — ensure migration tests pass when run with full suite. Options: re-run `fix_db2.py` before migration tests, or prevent lifespan `create_all` on `arqau.db` during test teardown, or add `arqau.db` cleanup to test setup
3. **Run focused Phase 1.2 tests** — `test_phase12_models`, `test_phase12_database`, `test_phase12_api`, `test_phase12_migration`, `test_alembic`
4. **Fix any concrete failures** from focused tests
5. **Run complete Phase 1.2 regression** — all tests, Python compile, git diff --check, alembic commands, fresh DB migration, legacy SQLite copy upgrade, downgrade/re-upgrade, legacy row-count preservation, backend startup, `/health`
6. **Verify PostgreSQL DDL compilation** (no live PostgreSQL — mark as NOT VERIFIED)
7. **Verify frontend production build** (`npm run build`)
8. **Produce Phase 1.2 Final Report**
9. **STOP before Phase 1.3**

---

## 9. Safety Rules (MUST Follow)

DO NOT:
- Change `User.id`
- Delete legacy tables
- Reset/discard current work
- Guess salary from `monthly_income_range`
- Modify EWA behavior
- Redesign auth
- Implement RBAC yet
- Redesign frontend
- Start Phase 1.3
- Weaken FK constraints to make tests pass
- Disable SQLite foreign keys
- Use fake PASS results
- Redo Phase 1.1
- Commit incomplete Phase 1.2 automatically

---

## 10. Quick Commands Reference

```powershell
# Check arqau.db state
python C:\Users\brawl\AppData\Local\Temp\kilo\check_arqau.py

# Fix arqau.db (legacy DB)
python C:\Users\brawl\AppData\Local\Temp\kilo\fix_db2.py

# Run focused tests
cd backend
python -m unittest tests.test_phase12_models -v
python -m unittest tests.test_phase12_database -v
python -m unittest tests.test_phase12_api -v
python -m unittest tests.test_phase12_migration tests.test_alembic -v

# Full suite
python -m unittest discover -s tests -v

# Compile check
python -m compileall backend/app backend/tests backend/alembic

# Alembic commands
python -m alembic history
python -m alembic heads
python -m alembic check
```
