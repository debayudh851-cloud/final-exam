# TalentDesk — AI-enabled recruitment portal

An integrated, locally executable Django 5 assessment prototype. HR can import CSV/Excel applications, inspect accepted/rejected rows, review rule/ML/resume scores, update screening stages, assign interviews, and view analytics. Interviewers see assigned slots and submit feedback. Admin controls all records.

## Open the running application

- Portal: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/api/docs/
- Django admin: http://127.0.0.1:8000/admin/
- Local test users: `hr`, `interviewer`, `admin`.
- Password for the seeded local test accounts: `CampusDemo!2026`. These are disposable assessment accounts, not production credentials.

Your PostgreSQL password is held only in the ignored local `.env`, not in this README or the source ZIP. The ZIP excludes `.env`, installed dependencies, logs, and uploaded media. `.env.example` describes configuration for a new checkout.

## Requirements

Python 3.13, PostgreSQL, and Redis. This workspace was built with PostgreSQL 18 and Django 5.2. Exact installed Python packages are in `requirements-lock.txt`; use `requirements.txt` for compatible ranges. TensorFlow runs on CPU. Dependencies and the NLTK resource require downloads during setup; the portal and Swagger then run locally without external APIs or CDN assets.

The application uses Django Templates, DRF, JWT, Celery/Redis, Pandas/NumPy, Scikit-learn/Matplotlib, NLTK, and TensorFlow/Keras. It uses no React, WebSockets, Docker, Kubernetes, cloud application services, or external LLM APIs.

## Clean setup (PowerShell, from the project directory)

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
```

Edit `.env`: set a random `DJANGO_SECRET_KEY` and your database username/password. Keep `DB_NAME=recruitment_portal` or choose a new dedicated name. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. PostgreSQL must already be running, and the database user must have database-creation permission for the helper (or create the named database manually).

```powershell
.\.venv\Scripts\python scripts/create_database.py
.\.venv\Scripts\python manage.py migrate
$env:DEMO_PASSWORD = 'CampusDemo!2026'
.\.venv\Scripts\python manage.py seed_demo
.\.venv\Scripts\python manage.py setup_nlp
.\.venv\Scripts\python manage.py train_ml
.\.venv\Scripts\python manage.py run_ann
.\scripts\install_redis.ps1
.\scripts\start.ps1
```

Migrations are included; `makemigrations` is needed only after changing models. Check with `python manage.py makemigrations --check --dry-run` and `python manage.py migrate --check`. `python manage.py createsuperuser` creates your own admin instead of the demo seed; a superuser bypasses the HR verification gate.

The Windows Redis helper downloads a checksum-verified **community Windows build** from [redis-windows](https://github.com/redis-windows/redis-windows/releases/tag/8.2.10), into `.tools/`, without installing a system service. The pinned SHA-256 is in the helper. It binds to loopback only. Standard Redis on Linux/WSL can be used instead; set `REDIS_URL` accordingly. [Redis’s Windows installation options](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-on-windows/) describe supported alternatives.

`start.ps1` launches hidden local Redis, Celery, and Django processes and checks server readiness. Logs/PIDs are in `logs/`. Stop them with `scripts/stop.ps1`. Do not run the launcher twice without stopping the recorded processes. An already-running Redis on port 6379 should instead be used with the manual commands below.

### Manual run commands (separate terminals)

```powershell
# Redis: after scripts/install_redis.ps1, from this directory
.\.tools\redis\Redis-8.2.10-Windows-x64-msys2\redis-server.exe --bind 127.0.0.1 --port 6379 --appendonly no
# Celery: Windows assessment worker
.\.venv\Scripts\python -m celery -A config worker --pool=solo --loglevel=info
# Django
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

Celery does not officially support Windows; this locally verified prototype uses the `solo` pool. A Linux/WSL worker can use the normal worker pool. See [Celery’s Windows support statement](https://docs.celeryq.dev/en/stable/faq.html#does-celery-support-windows). No Docker is needed.

## Walk through the portal

1. Sign in as `hr`. Open **Import applications**, select `samples/candidates.csv`, and submit. On a clean database, 13 rows are accepted and 3 rejected. Download both exports.
   The overview shows overall salary total/minimum/maximum/average and all five aggregates per role. **Minimum applications per role** filters grouped roles using a real SQL `HAVING` clause; overall totals continue to include every candidate.
2. Open the batch’s candidates. The batch is remembered in the session; clear it through **Show all batches** or **Reset**. The role filter is remembered in an HTTP-only cookie.
3. Open a candidate to inspect rule results, probability, resume keyword score, and POS tags. Review before setting **Shortlisted**. **Recalculate scores** refreshes scores without changing the HR stage.
4. Assign an available interview slot for that candidate’s role. Slot options load using AJAX. Seeded slots are future slots; Admin can create others in Django admin, or HR/Admin can POST `/api/interview-slots/create/`.
5. Sign in as `interviewer`, open **Interviews**, and submit feedback for an assigned slot. The recommendation updates the candidate’s stage. Other interviewers’ work is hidden.
6. Upload `samples/large_batch.csv` (120 rows) to exercise Celery. Files of at least 100 rows, or explicitly checked background jobs, are queued. The page polls status/progress. Accepted/rejected downloads are protected.
7. Add/edit a candidate to try the CSRF-protected duplicate-email AJAX check. Upload `samples/resume.txt` and `samples/candidate.png` for optional media. Media is served through protected views rather than public media URLs.

New HR registration is at `/accounts/register/` or `/api/auth/register/`. It always creates the HR role. A hashed six-digit OTP expires in 10 minutes, permits five attempts, and is erased on success. The default **console email backend** writes the code to the server terminal/log; it does not send email externally. Enter it at `/accounts/verify/` or `/api/auth/verify/`. For actual email delivery, configure SMTP environment variables in `config/settings.py`. Admin assigns Interviewer/Admin roles; registration cannot escalate privileges.

## Input contract and repeatability

Required columns: `candidate_name,email,phone,college,applied_role,skills,experience_months,notice_period_days,expected_salary,historical_selection_status`. Optional: `resume_text,portfolio_url`. CSV must be UTF-8; Excel must be `.xlsx`. `.xls` is not supported. Role may be an existing name or code. The implementation accepts at most 20 MB and 50,000 rows per batch.

Emails are lowercased and unique across the portal (one application per email in this prototype). Phones allow 10–15 digits and an optional leading `+`. Names/skills are normalized; malformed, negative, non-finite, fractional integer fields and overlong strings are rejected. All applicable errors appear on each rejected row. Existing candidates are never overwritten by imports. Re-uploading the same data rejects duplicates; replaying a completed Celery batch is a no-op. Accepted/rejected downloads use their prescribed filenames even though storage adds unique suffixes. CSV cells that could be interpreted as spreadsheet formulas are escaped.

International phone prefixes `00` and a pasted full-width plus are normalized to `+`. The upload path uses reusable helpers in `ingestion/processing.py`: recursive field-error formatting, shallow copying of raw export rows, a nonlocal row counter, iterator processing, and immutable accepted/rejected counts combined with operator overloading. Each CandidateValidator deep-copies its nested module-level policy so one instance cannot alter another. `python -m ingestion.python_concepts` walks through these actual production helpers.

## APIs and Postman

Import `postman_collection.json` into Postman. Set its `password` variable to the local test password and run the collection in order. Login stores the JWT access/refresh tokens automatically. CRUD checks create and delete only a synthetic API candidate. The collection tests expected statuses and includes authorization failures, prediction, and refresh revocation. `evidence/postman_run.json` records the verified Newman run; `evidence/http_smoke.json` records real HTTP/service checks. Newman is [Postman’s command-line collection runner](https://learning.postman.com/docs/reference/newman-cli/installing-running-newman/). To reproduce with Node/npm installed: `npm install --prefix .tools/newman newman`, then set `DEMO_PASSWORD` and run `node scripts/run_postman.cjs`. Node/Newman are only API-test tools; the application remains a Python/Django project.

For protected calls, send `Authorization: Bearer <access>`; JSON calls also need `Content-Type: application/json`. Upload uses `multipart/form-data` with `file` and optional `background`. Session browser forms use CSRF tokens; JWT APIs do not use browser session authentication.

Two additional browser-session-protected JSON views are `/dashboard/json/candidates/` (every candidate, including rejected records, with no result cap) and `/dashboard/json/candidates/<id>/` (one candidate). The DRF `/api/candidates/` endpoint retains normal pagination.

| Method | URL | Body / expected response |
|---|---|---|
| POST | `/api/auth/login/` | `{"username":"hr","password":"<test password>"}` → 200 access/refresh/role |
| GET | `/api/roles/` | 200 paginated roles; hyperlinked serializer supplies `url` |
| POST | `/api/candidates/` | Candidate fields and integer `applied_role` ID → 201 |
| GET | `/api/candidates/<id>/` | 200 candidate; unknown ID → 404 |
| PUT/PATCH | `/api/candidates/<id>/` | Full/partial fields → 200; invalid numbers → 400 |
| DELETE | `/api/candidates/<id>/` | 204 |
| POST | `/api/batches/upload/` | Multipart `file` → 201 completed or 202 queued; failed processing/publish → 503 |
| GET | `/api/batches/<id>/status/` | 200 status, progress, counts, error, exports |
| GET | `/api/batches/<id>/download/accepted/` | Protected accepted CSV; rejected route analogous |
| GET | `/api/screening-results/` | 200 paginated screening results |
| GET | `/api/interview-slots/` | All slots for managers, assigned slots for interviewers |
| POST | `/api/interview-slots/create/` | Role, interviewer, start/end, location → 201 |
| POST | `/api/interviews/assign/` | `{"candidate":1,"slot":1}` → 200; unavailable/wrong role → 400 |
| POST | `/api/interview-feedback/` | Slot, rating 1–5, comments, recommendation → 201 |
| POST | `/api/screening/predict/` | See JSON below → 200 probability/shortlisted/model version |
| POST | `/api/screening/nlp/` | `{"resume_text":"Python and Django","role":1}` → 200 tokens/POS/vector/matches |
| POST | `/api/auth/refresh/` | `{"refresh":"<refresh>"}` → 200 rotated pair; invalid/revoked → 401 |
| POST | `/api/auth/logout/` | `{"refresh":"<refresh>"}` → 200 refresh revoked |
| GET | `/api/candidates/` with no/invalid/expired token | 401; interviewer → 403 |

Example prediction body:

```json
{"experience_months":12,"notice_period_days":30,"expected_salary":500000,
 "skills":"python, django, sql","applied_role":"Python Developer"}
```

HR/Admin manage candidates, imports, screening, ML/NLP, and slot assignment. Interviewers can view their assigned slots and submit their own feedback; Admin can submit all feedback. Unverified users cannot access protected pages/APIs. Logout blacklists refresh tokens; already issued access tokens expire in 15 minutes. Swagger is public local documentation; operations remain protected. Generate a validated offline schema with `python manage.py spectacular --file openapi.yaml --validate`.

## ML, NLP, and Keras

`samples/training.csv` has 240 **synthetic** records. Labels are `historical_selection_status` selected/rejected; the generator documents the synthetic rule and 12% label noise. It is not representative hiring data.

The pipeline removes duplicate emails and target/identity/leakage fields, coerces numeric values, handles missing values with train-fitted imputers, caps outliers using training-only 1st/99th percentiles, standardizes numeric features, and one-hot encodes job role. Features are experience, notice period, salary, unique skill count, and role. An identical stratified 180/60 split compares Logistic Regression and Random Forest by accuracy, precision, recall, F1, and ROC AUC. The demo selects the better F1/AUC and persists a trusted local joblib artifact. Prediction loads it once per process. Restart Django/Celery after retraining so workers load the new artifact.

`artifacts/ml_metrics.json` and `model_comparison.png` report comparison results. `notes.txt` explains limitations: this holdout is used for model choice and does not provide an independent final evaluation.

NLTK `wordpunct_tokenize` and the English POS tagger analyze resume text. A single-resume TF-IDF vector makes numerical mechanics visible; its coordinates are not a cross-document semantic similarity model. Case-insensitive word-boundary matches against role skills produce a 0–100 keyword percentage. Missing text returns empty features and zero. Original resume text is retained.

The Keras prototype uses the same five raw features, six encoded input values for the seeded roles, 16/8 ReLU hidden units, and one sigmoid output. It trains via CPU minibatches, saves `ann.keras` plus preprocessing, reloads the ANN, and verifies a prediction. `artifacts/ann_metrics.json` records execution; small synthetic accuracy is not production evidence.

## Verification and submission

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test recruitment --noinput
.\.venv\Scripts\python -m ingestion.python_concepts
$env:DEMO_PASSWORD = 'CampusDemo!2026'
.\.venv\Scripts\python scripts/smoke_test.py
.\.venv\Scripts\python scripts/verify_gaps.py
.\.venv\Scripts\python scripts/check_sql.py
.\.venv\Scripts\python scripts/package_submission.py
```

The tests create a separate `test_recruitment_portal` database. The DB user needs test-database creation permission. Test cache uses memory so unit tests are isolated; the HTTP smoke checks use real Redis/Celery/PostgreSQL. Smoke creates fresh synthetic addresses each run, so it does not delete existing candidate records.

The 19 tests cover validation, duplicates, optional/punctuation resume text, protected routes, invalid/expired tokens, OTP and role escalation, CSRF AJAX, CRUD, interview permissions, repeatable inference, atomic failed uploads, completed-task replay, all-candidate JSON beyond 100 rows, salary aggregates/HAVING, policy isolation, and rejected-row progress/export preservation. See `evidence/verification.md` for actual run evidence and `coverage.md` for requirement-to-code mappings.

The packaged source is `recruitment_portal_submission.zip`, with migrations, SQL, sample CSV/Excel/media, Postman collection, README, notes, and evidence. Generated model/metrics artifacts are included; regenerate them with the documented commands. Uploaded candidate media and local secrets are excluded.

The ZIP has also been extracted into a fresh folder and checked against a newly created temporary PostgreSQL database: migrations, seed, NLP setup, page rendering, 13 accepted/3 rejected upload, packaged-model prediction, and SQL all passed. `evidence/clean_checkout.json` records this check. It reused the verified virtual environment; the temporary database was removed afterwards. Reproduce it with `python scripts/verify_clean_checkout.py` after packaging.

## Background work, cache, and viva

A synchronous upload holds its HTTP request until parsing/inserts/scoring finish. Celery returns a batch ID immediately, processes the saved upload, and records queued/processing/completed/failed state. Progress is written through a separate PostgreSQL connection every 25 rows, visible while the candidate transaction remains atomic. An unexpected failure rolls candidate inserts back and exposes a sanitized error. Failed batches can be retried from the portal. If a worker is killed, stop it and use `python manage.py recover_batch <id> --worker-stopped` after ten minutes, then restart/retry.

Redis caches the top ten shortlisted candidates per role for five minutes. Creation, editing, rescreening, stage changes, assignment, deletion, and feedback invalidate affected role keys after successful database work. Cache failure falls back to ORM reads; a broker failure marks uploads failed.

API rate limits use a separate process-local cache so a Redis outage can still reach the upload handler and record a useful failed status. The local prototype has one HTTP server; a multi-server deployment would need coordinated throttling.

Processes have separate memory and can run CPU work in parallel; threads share memory and commonly help I/O concurrency. This Windows demo’s solo Celery worker executes one task at a time, separate from the HTTP server. Celery is the required background mechanism; no extra distributed system is added.

GET displays/retrieves data. POST changes state and checks forms/serializers; PUT/PATCH update resources and DELETE removes records. Django MVT routes requests to views, uses models/ORM for storage, and templates for presentation. Function and class based views coexist; custom middleware logs method/path/timing/role and protects dashboard routes without intercepting login/static/admin/APIs.
