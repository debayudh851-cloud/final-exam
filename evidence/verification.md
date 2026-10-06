# Local verification — 5 October 2026 (Asia/Kolkata)

Verified on Windows with Python 3.13.11, Django 5.2.17, PostgreSQL 18, portable Redis 8.2.10, and a Celery 5.6.3 solo worker.

| Check | Result |
|---|---|
| Django system checks | No issues |
| PostgreSQL migrations | Both app migrations applied; no pending changes |
| Dependency consistency | pip check passed |
| Regression/integration suite | 19 tests passed; separate temporary PostgreSQL test database |
| Assessment gap checks | 15 targeted live checks passed: unrestricted candidate JSON, salary aggregates, GROUP BY/HAVING filter, isolated validation, rejected exports, and real Celery processing; gap_checks.json |
| Real HTTP and services | 33 checks passed; evidence/http_smoke.json |
| CSV initial batch | 13 accepted / 3 rejected; downloads verified |
| Excel duplicate replay | 0 accepted / 16 rejected |
| Real Celery large batch | 120 accepted; queued → processing → completed |
| Real Celery malformed-source failure | FAILED with a sanitized visible error; celery_failure.json |
| Postman collection via Newman | 14 requests, 14 status assertions, no failures; postman_run.json |
| Raw SQL | All 12 submitted statements executed read-only; sql_checks.json |
| ML | Logistic Regression and Random Forest trained/evaluated; metrics and Matplotlib plot saved |
| NLTK | Tokenization, English POS, TF-IDF vector, skill matches, and blank-input API tested |
| Keras | ANN trained/saved/reloaded; prediction verified; ann_metrics.json |
| Browser | HR sign-in, dashboard, candidate list/detail, dynamic slot options; desktop/narrow layout checked |
| Source archive | ZIP integrity and secret exclusion checked by packaging helper |
| Fresh source/database | ZIP extracted into a fresh folder; migrations, seed, NLP setup, portal rendering, 13/3 upload, model inference, and SQL passed; clean_checkout.json |

The intentional worker-failure demonstration remains visible as a failed batch in the local portal. All stored candidates are synthetic. ANN/ML metrics describe demo mechanics, not real hiring quality. PostgreSQL password, JWT tokens, OTPs, and uploaded personal files are not included in saved evidence.

The fresh-source check used the already installed, verified Python virtual environment, not a second dependency installation. Its temporary PostgreSQL database was created solely for the check and removed afterwards.
