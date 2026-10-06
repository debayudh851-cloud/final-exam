# AI Enabled Recruitment Portal Assessment Guide

## Purpose and assessment scope

This guide translates **Question Paper 1: AI-Enabled Recruitment Screening and Interview Intelligence Portal** into a complete implementation checklist and study guide. The paper sets one integrated, scenario-based machine test covering the Day 1–Day 73 syllabus. The prototype must run locally, use the stated stack, and combine candidate ingestion, screening, interviews, APIs, background processing, analytics, ML, NLP, and a minimal deep-learning component in one Django project.

The assessment is worth **100 marks**, lasts **3 hours**, and includes a viva. Treat each requirement below as part of the same solution. The evaluator expects working evidence, not just a design description. Build a small, coherent prototype with clear limitations rather than a collection of disconnected demonstrations.

## Assessment at a glance

| Item | Requirement |
|---|---|
| Course | Django 5 with ML/AI |
| Assessment | 4th Assessment — Final Integrated Machine Test |
| Coverage | Day 1 to Day 73 / full syllabus |
| Questions | One integrated scenario-based coding question |
| Marks | 100 |
| Duration | 3 hours |
| Viva | Yes |
| Deployment target | Local machine |

## Business problem

A product company recruits Python/Django freshers from several campuses. HR imports thousands of candidate records from CSV or Excel files and receives resume text snippets. The internal portal must validate and clean applications, screen candidates with business rules and ML scoring, analyze resume text, organize interview slots and feedback, and provide protected APIs to HR users and interviewers.

## Mandatory technology and boundaries

Use only the listed syllabus stack and keep the project locally executable:

- Python 3 and Django 5
- Django Templates for the web interface; Django REST Framework (DRF) for APIs
- PostgreSQL, Django ORM, migrations, and a separate `sql_queries.sql` file for requested raw queries
- JWT or Token Authentication, role-based access, and email or OTP verification for new HR users
- Celery for requested asynchronous work; Redis as broker and for caching
- NumPy, Pandas, Matplotlib, and Scikit-learn for ML/data work
- NLTK for NLP
- TensorFlow/Keras for a minimal executable ANN or clearly executable prototype
- Postman and Swagger for API testing/documentation

**Do not use:** React, WebSockets, Docker, Kubernetes, cloud services, external LLM APIs, or other out-of-syllabus topics. Keep secrets out of source code; use environment variables. Include a README and working migrations. A broken or non-running project, hard-coded secrets, copied code the student cannot explain, or a missing README risks heavy penalties.

## Integrated system flow

1. HR signs in and uploads a candidate CSV/Excel file.
2. The ingestion utility checks format, columns, empty input, duplicates, and field validity.
3. Clean rows are accepted; invalid rows are exported with reasons. Large batches can be sent to Celery.
4. Valid candidates and their application batch are saved through Django ORM.
5. Rule-based screening, ML shortlist probability, and resume keyword/NLP scoring produce screening results.
6. HR reviews candidates and filters by role/status. The system remembers the selected role in a cookie and current batch in a session.
7. HR/interviewers view role-specific interview slots, submit feedback, and update screening stages according to their permissions.
8. Secured DRF endpoints expose candidate, batch, screening, feedback, and ML functions. APIs are documented in Swagger and demonstrated in Postman.
9. A dashboard reports role-wise and screening statistics using ORM/SQL aggregation.

## Suggested project structure

This is an implementation suggestion to keep responsibilities understandable. The paper does not prescribe exact app names or filenames.

```text
recruitment_portal/
├── manage.py
├── config/                 # settings, root URLs, WSGI/ASGI
├── accounts/               # user roles, registration, verification, auth APIs
├── recruitment/            # roles, candidates, batches, screening, interviews
├── ingestion/              # CSV/Excel validation, cleaning, accepted/rejected output
├── screening/              # rules, ML training/inference, NLTK, Keras prototype
├── templates/              # Django templates
├── static/                 # CSS and JavaScript
├── media/                  # uploaded resumes/images in local development
├── sql_queries.sql         # required PostgreSQL examples
├── notes.txt                # assumptions, limitations, implementation notes
└── README.md                # setup, run, migrations, credentials, testing
```

## Data input contract

The upload utility must accept CSV and Excel files with these fields:

| Field | Example/validation intent |
|---|---|
| `candidate_name` | Required text; trim and normalize case as appropriate |
| `email` | Required; validate with a regular expression; normalize case |
| `phone` | Required; validate with a regular expression; normalize permitted characters |
| `college` | Text; trim and normalize |
| `applied_role` | Must refer to a known or resolvable job role |
| `skills` | Text/list-like input; normalize and split into skills |
| `experience_months` | Numeric; reject malformed or invalid values |
| `notice_period_days` | Numeric; reject malformed or invalid values |
| `expected_salary` | Numeric; reject malformed or invalid values |
| `resume_text` | Optional text; safely support missing or blank values |
| `portfolio_url` | Optional URL/text field; validate as appropriate to the prototype |
| `historical_selection_status` | Normalize and validate against supported status values |

Produce both `accepted_rows.csv` (clean accepted rows) and `rejected_rows.csv` (rejected rows plus a reason for each error). Design validation so a row with multiple problems can report useful reason-wise errors. The process must safely handle invalid format, missing required columns, empty uploads, duplicate rows, invalid numeric values, and invalid email/phone/code patterns.

## Requirement-by-requirement implementation checklist

### 1. Candidate ingestion and Python automation

- [ ] Read CSV and Excel input and check the extension/content and required columns before processing.
- [ ] Handle empty files and missing columns without crashing.
- [ ] Validate email and phone using regular expressions.
- [ ] Clean strings using `strip()`, case normalization, `split()`, and `join()`; demonstrate indexing, slicing, `removeprefix()`, and `removesuffix()` where they naturally apply to inputs.
- [ ] Check numeric fields and report invalid values per row.
- [ ] Detect duplicates and define the duplicate key (for example, normalized email); record the reason in rejected output or skip according to a documented rule.
- [ ] Write cleaned rows to `accepted_rows.csv` and invalid rows with reason-wise errors to `rejected_rows.csv`.
- [ ] Keep ingestion repeatable and avoid corrupting existing database records.

The paper explicitly expects the following Python syllabus concepts to appear **where they naturally fit**. Include a small, meaningful use and be prepared to explain it; avoid inserting concepts into production flow when they have no reasonable purpose.

| Required concept | Possible sensible use in this project |
|---|---|
| Lists, tuples, sets, frozensets | Rows/errors; immutable required-field definitions; unique normalized skills |
| Dictionaries | Row data, validation errors, field mappings |
| Dictionary/set comprehensions | Build normalized maps or unique skill sets |
| Iterators | Process rows incrementally to reduce memory use |
| `while`, `break`, `continue` | Controlled row processing or retry/validation loops where suitable |
| Shallow and deep copy | Safely copy nested row/configuration structures; explain the difference |
| Decorators | Timing/logging or reusable validation wrapper |
| Recursion | A small justified nested-structure helper; avoid artificial recursion |
| `*args`, `**kwargs` | Reusable validator/logger helper with flexible arguments |
| `lambda` | A short key function for sorting/filtering |
| Local/global/nonlocal | Demonstrate scope in a contained helper/example; avoid global mutable state |
| Inheritance | Shared base validator/model/service behavior where appropriate |
| Operator overloading | A small domain object (e.g., score aggregation) only if clear and explainable |
| User-defined exceptions | Invalid file, missing column, or row validation exceptions |

### 2. Django portal, models, and admin

Create meaningful models and relations for at least:

- [ ] `JobRole`
- [ ] `Candidate`
- [ ] `ApplicationBatch`
- [ ] `ScreeningResult`
- [ ] `InterviewSlot`
- [ ] `InterviewFeedback`

Design sensible foreign-key/one-to-many relationships (for example, a role has many candidates/applications; a batch records its uploaded candidates; a candidate can have screening results and interview activity). Add appropriate timestamps, status choices, uniqueness rules, and optional fields. Do not make optional resume/media/text required.

Customize Django admin with:

- [ ] useful `list_display` columns
- [ ] filters
- [ ] searchable fields
- [ ] fieldsets that group related fields

Implement both function-based views and class-based views for the required work:

- [ ] upload candidate files
- [ ] list candidates
- [ ] view candidate details
- [ ] edit screening status
- [ ] delete invalid records

Use Django Template Language and demonstrate:

- [ ] context variables, `{% for %}`, `{% if %}` / `{% else %}`
- [ ] URL reversing and redirects
- [ ] correct GET/POST handling
- [ ] forms or ModelForms with validation and error display
- [ ] static CSS/JavaScript
- [ ] media upload and resume/image file support
- [ ] safe behavior when optional text or media is absent

### 3. AJAX, CSRF, cookies, sessions, and middleware

- [ ] Use AJAX to check whether an email is already registered before final form submission.
- [ ] Use AJAX to load interview slots dynamically after a role is selected.
- [ ] Protect AJAX POST requests with Django CSRF handling; return structured JSON responses and handle errors in the browser.
- [ ] Use a cookie to remember the last selected role filter and restore it on the next visit.
- [ ] Store the HR user's currently selected screening batch in the session.
- [ ] Create custom middleware that records request path, request method, processing time, and user role.
- [ ] Middleware must also block unauthenticated access to internal dashboard URLs. Ensure login/static/admin/API behavior is not accidentally blocked by the dashboard rule.

### 4. PostgreSQL, ORM, SQL, and reports

- [ ] Configure PostgreSQL using environment-based settings.
- [ ] Create and apply migrations; include a clear migration workflow in the README.
- [ ] Use model relationships and Django ORM for routine application work.
- [ ] Demonstrate `get()`, `filter()`, `exclude()`, ordering, slicing, and JSON responses for an individual candidate and for candidate collections.
- [ ] Keep requested raw PostgreSQL examples in a separate file named exactly `sql_queries.sql`.

The SQL file must contain relevant, runnable examples for all of these requirements:

1. Candidate search.
2. Role-wise candidate counts.
3. Selected/rejected aggregation.
4. Salary range using `BETWEEN`.
5. Skills search using `LIKE`.
6. `INNER JOIN` between candidates and roles.
7. `FULL OUTER JOIN` to show role/candidate availability.
8. `NATURAL JOIN` where suitable (if schema makes it unsafe or unsuitable, explain the limitation and provide a safe equivalent/example).
9. `UNION ALL` for selected and waitlisted candidates.
10. `INTERSECT` for candidates matching both Python and Django skills.
11. Dashboard summary using `COUNT`, `SUM`, `MIN`, `MAX`, `AVG`, `GROUP BY`, and `HAVING`.
12. Include relevant `WHERE`, `AND`/`OR`, `LIMIT`, and `ORDER BY` examples as required by the submission instructions.

Use consistent table/column names between the models and SQL examples, or state any SQL schema assumptions in comments. The dashboard should show useful summary figures, such as candidate counts and salary statistics, grouped by role or status.

### 5. DRF APIs, authentication, and permissions

Expose and test APIs for:

- [ ] login
- [ ] registration
- [ ] logout
- [ ] candidate CRUD
- [ ] batch upload status
- [ ] screening result list
- [ ] interview feedback submission
- [ ] secured ML prediction from candidate features, returning a predicted shortlist result and a score/confidence

Implementation requirements:

- [ ] Serializers for GET/POST/PUT/DELETE workflows; use `ModelSerializer` validation.
- [ ] At least one endpoint using `HyperlinkedModelSerializer`.
- [ ] JWT **or** Token Authentication. If JWT is chosen, support access and refresh token flow.
- [ ] Roles: HR, Interviewer, and Admin.
- [ ] Custom permissions that restrict actions by role (e.g., HR manages candidates/batches, interviewers access assigned interview work and submit feedback, Admin manages all records).
- [ ] Email verification or OTP verification for new HR users before secured API access.
- [ ] Invalid/expired tokens return appropriate authentication errors; unauthorized users cannot access protected pages or APIs.
- [ ] Swagger API documentation.
- [ ] Demonstrate at least five API requests in Postman, with request method, URL, headers/body, and expected response/status documented in README.

Suggested endpoint map (illustrative; exact paths are implementation choices):

| Purpose | Example route | Access idea |
|---|---|---|
| Register | `/api/auth/register/` | Public, new HR requires verification |
| Verify email/OTP | `/api/auth/verify/` | Verification token/code |
| Login | `/api/auth/login/` | Public |
| Refresh access token | `/api/auth/refresh/` | Valid refresh token |
| Logout | `/api/auth/logout/` | Authenticated |
| Candidate list/create | `/api/candidates/` | Authenticated, role permission |
| Candidate detail/update/delete | `/api/candidates/<id>/` | Authenticated, role permission |
| Batch status | `/api/batches/<id>/status/` | HR/Admin |
| Screening results | `/api/screening-results/` | HR/Admin, interviewer as allowed |
| Feedback submit | `/api/interview-feedback/` | Interviewer/Admin as allowed |
| ML prediction | `/api/screening/predict/` | Authenticated, permitted role |
| Swagger | `/api/docs/` | Local documentation endpoint |

Treat these route names as examples, not fixed requirements. Document the actual routes and role policy used.

### 6. Celery, Redis, and asynchronous work

- [ ] Process large candidate uploads asynchronously through Celery.
- [ ] Use Redis as the Celery broker.
- [ ] Save upload job status and progress so the UI/API can report queued, processing, completed, or failed work.
- [ ] Make task failures visible through status/progress records or API responses; capture a useful error state without leaking secrets.
- [ ] Cache top shortlisted candidates per role using Redis and define cache invalidation/update behavior after screening changes.
- [ ] Include Redis and Celery start commands in README.
- [ ] Explain the difference between doing a long upload inside an HTTP request and queueing it as background work.
- [ ] Be ready to explain multiprocessing versus multithreading. This is a rubric/viva concept; use it where taught and do not introduce an out-of-syllabus distributed system.

### 7. ML pipeline and prediction endpoint

Use Pandas, NumPy, Matplotlib, and Scikit-learn. Train a model to estimate shortlist probability from cleaned candidate features. The implementation must show the following steps:

- [ ] Load and inspect the training data.
- [ ] Handle missing values.
- [ ] Remove duplicates.
- [ ] Remove useless/non-predictive columns (such as identifiers or leakage fields) and explain why.
- [ ] Treat outliers with a documented, simple method.
- [ ] Encode categorical variables.
- [ ] Select features and explain the chosen features.
- [ ] Split data into training and test sets.
- [ ] Train at least two algorithms chosen from Logistic Regression, Random Forest, SVM, Naive Bayes, and KNN.
- [ ] Evaluate and compare models using suitable classification metrics; include a plot made with Matplotlib where useful.
- [ ] Select and persist/load the chosen model in a repeatable way appropriate to the course environment.
- [ ] Provide a secured DRF endpoint accepting candidate features and returning prediction plus a probability/score.
- [ ] Make inference callable repeatedly without changing existing candidate records.

Important: training labels must be defined from available historical selection data or another explicitly documented label rule. A tiny sample dataset can demonstrate executable mechanics, but do not present its score as evidence of real hiring accuracy. State dataset size, assumptions, limitations, and the need for representative labeled data in `notes.txt`.

### 8. NLTK resume analysis

- [ ] Tokenize `resume_text` with NLTK.
- [ ] Convert text to numerical vectors (use an appropriate vectorizer/features approach and explain it).
- [ ] Perform POS tagging.
- [ ] Compute a skill-keyword match score against the selected role's required skills.
- [ ] Handle missing/blank resume text safely.
- [ ] Keep processing repeatable and avoid mutating the stored original resume text.

### 9. TensorFlow/Keras deep-learning component

- [ ] Implement a minimal ANN for shortlist or resume-score classification, or a clearly executable prototype.
- [ ] Explain inputs, target, output, and how the model is invoked.
- [ ] Ensure the component can run locally with the documented dependencies and data shape.
- [ ] If the available sample data is too small for meaningful learning, say so in `notes.txt`; demonstrate the execution path without claiming production quality.

### 10. Edge cases and safety checks

The application must handle all of the following safely:

- [ ] Unsupported or invalid file format.
- [ ] Missing required columns.
- [ ] Empty uploaded file.
- [ ] Duplicate rows/candidates.
- [ ] Invalid numeric values.
- [ ] Invalid email, phone, or code/pattern values.
- [ ] Unauthenticated access to protected pages/APIs.
- [ ] Invalid and expired tokens.
- [ ] Missing optional resume text or media.
- [ ] Repeated ML/NLP/DL calls without corrupting database records.
- [ ] Celery task failure visible via status/progress or API response.

## Required submission files and local run evidence

Submit a zip of the complete Django source project and include:

- [ ] `README.md` — prerequisites; virtual environment/dependency installation; environment variables; PostgreSQL/database creation; migrations; superuser/admin test credentials (test-only); local server command; Redis and Celery commands; API URLs and testing steps.
- [ ] `sql_queries.sql` — all requested SQL examples.
- [ ] `notes.txt` — assumptions, known limitations, and how ML/NLP/DL were implemented.
- [ ] Sample CSV/Excel dataset.
- [ ] At least one sample media/image file if media upload is required by the implementation.
- [ ] Complete Django source as a zip file.

Before submission, verify this local sequence from a clean checkout/environment:

1. Set required environment variables without committing secrets.
2. Create/configure the PostgreSQL database.
3. Install requirements.
4. Run `python manage.py makemigrations` if needed, then `python manage.py migrate`.
5. Create a superuser or document provided test-only admin credentials.
6. Start Redis.
7. Start a Celery worker.
8. Start Django locally.
9. Open the portal and test file upload, accepted/rejected output, candidate listing, screening, and interview flow.
10. Open Swagger and execute API requests in Postman, including an unauthorized/invalid-token case and at least five successful or expected-error requests.
11. Confirm Celery status progresses and failures are visible.
12. Run the ML, NLP, and Keras examples and verify the secured prediction endpoint.
13. Re-run migrations and key processing functions to ensure there are no broken migrations or duplicate/corrupt records.

## Evaluation rubric and how to prove coverage

| Evaluation area | Marks | Expected evidence to show |
|---|---:|---|
| Python core scripting, validation, OOP, decorators, recursion, exceptions, collections, string handling | 10 | Running scripts, validators, custom exceptions, OOP use, clean Python |
| Django MVT, templates, forms/ModelForms, static/media, admin customization, AJAX, CSRF, cookies, sessions, middleware, CBV | 20 | Working UI, admin, forms, templates, AJAX, security, middleware, upload flow |
| PostgreSQL, raw SQL, models, migrations, ORM QuerySets, JSON responses | 15 | Correct schema, migrations, ORM usage, SQL file, analytics, JSON responses |
| DRF serializers, API CRUD, validation, Postman/Swagger, JWT/Token auth, roles, custom permissions, email/OTP verification | 15 | Secured APIs, serializers, role permissions, token flow, verification, Swagger/Postman proof |
| Asynchronous execution, Celery worker, Redis broker/cache, multiprocessing vs multithreading understanding | 10 | Working task/worker, Redis usage, progress/status, cache, explanation |
| Data processing, visualization, feature engineering, ML training/evaluation/deployment | 15 | Executable pipeline, preprocessing, training, metrics, prediction endpoint |
| NLP using NLTK plus TensorFlow/Keras deep-learning component | 10 | Working NLTK pipeline and minimal Keras model/prototype with explanation |
| Code quality, project structure, README, edge cases, and viva readiness | 5 | Readable code, setup documentation, explicit assumptions, clear viva answers |

## Viva preparation

Answer in terms of the actual project implementation. Do not claim a feature exists if it is only planned.

### Why GET and POST are used differently

- **GET** retrieves data or displays a page and should not change server state: examples include candidate lists, details, available slots, and status reports.
- **POST** submits new data or requests a state-changing action: examples include registration, login, uploads, feedback submission, and candidate creation.
- **PUT/PATCH** updates existing resources; **DELETE** removes a resource when authorized. Explain how the API serializer and permissions validate each action.

### MVT flow for candidate upload

The browser sends a request to a URL. Django resolves it to the upload view. The view checks request method and authentication, validates the form/file, calls the ingestion service or queues a Celery task, saves results/status through models and ORM, then renders a template or returns JSON/redirects. The template presents the form, validation errors, and batch status. Explain where the model, template, and view each do their work.

### Authentication, refresh tokens, and custom permissions

Explain how a user obtains an access token after login, how the access token authenticates protected API requests, and how a refresh token obtains a new access token when supported by the chosen JWT setup. Explain token expiry/invalid-token responses, how HR/Interviewer/Admin roles are represented, and how each custom permission checks the role and action. Explain the HR verification gate before API access.

### Why Celery is used

Large uploads and screening can take longer than a normal web request. A web request that waits for all rows can time out and leave the user without progress. Celery lets the request enqueue work and return a batch/task identifier while a worker processes it. The database stores progress/failure status, and Redis brokers the queued work. Explain how retries/failures are represented in the actual prototype.

### Feature engineering and model choice

Name the features actually used (for example, experience, notice period, salary, skills-derived features, college/role categories), the target label source, missing-value and outlier handling, encoding, train/test split, and evaluation metrics. Explain why two candidate algorithms were compared and why the final one was selected. Note any small-sample limitations.

### Resume text features

Explain how NLTK tokenization/POS tagging works in the implemented pipeline, how text becomes numerical features, and how role-specific skill matches contribute to the score. Clarify that the original text is retained and optional missing text is handled.

### Multiprocessing and multithreading

Be ready to distinguish processes (separate memory spaces, useful for CPU-bound parallel work subject to overhead) from threads (shared process memory, useful for concurrent I/O-bound work). Relate the answer to this project only if the implementation or syllabus example uses them; Celery is the required background-job mechanism here.

## Three-hour build order

This is a prioritization aid, not a change to the paper's requirements. Aim to leave a runnable, integrated prototype and reserve time to verify it.

1. **Foundation:** project/settings, PostgreSQL connection, models, admin, migrations, sample data.
2. **Working portal:** upload validation, accepted/rejected CSVs, candidate list/detail, status edit, basic templates.
3. **Security and APIs:** auth/roles/serializers, candidate CRUD, batch/screening/feedback endpoints, Swagger, Postman proof.
4. **Async and integrations:** Celery upload status and Redis cache; role slot/email AJAX, cookie/session, middleware.
5. **ML/NLP/DL:** executable small pipelines and secured prediction endpoint; document limitations.
6. **Submission and viva:** SQL file, README, notes, edge-case pass, clean startup verification, zip project.

If time is tight, keep the core flow executable and clearly label a minimal prototype where the paper permits one (notably the Keras component). Do not silently omit a mandatory requirement; list any unfinished point honestly in `notes.txt` and be ready to explain it.

## Final completeness checklist

- [ ] One integrated Django 5 project; local run verified.
- [ ] Candidate CSV/Excel ingestion, field cleaning, validation, and accepted/rejected exports.
- [ ] All named Python concepts addressed naturally and explainably.
- [ ] Six required domain models, useful admin, FBV and CBV, templates/forms, static/media.
- [ ] Duplicate-email and dynamic-slot AJAX with CSRF; role cookie and batch session; custom middleware.
- [ ] PostgreSQL migrations, required ORM patterns, candidate JSON responses, analytics, all SQL examples.
- [ ] Required DRF endpoints, serializer types/validation, JWT or token authentication, roles/permissions, HR verification, Swagger, five Postman requests.
- [ ] Celery large-upload task, Redis broker/cache, visible progress/failure, README commands.
- [ ] ML preprocessing, two algorithms, evaluation, Matplotlib output, secured prediction endpoint.
- [ ] NLTK tokenization, vectors, POS tags, skill matching.
- [ ] Executable TensorFlow/Keras ANN/prototype and explanation.
- [ ] Edge cases covered; optional text/media safe; repeated model calls do not alter records.
- [ ] README, `sql_queries.sql`, `notes.txt`, sample data/media if used, and zipped source included.
- [ ] Viva explanations match what the code actually does.
