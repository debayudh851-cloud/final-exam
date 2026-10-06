# Requirement coverage and viva map

| Assessment area | Working implementation / evidence |
|---|---|
| CSV/Excel parsing, missing columns, blank files, bad format, limits | `ingestion/service.py::read_upload`; `UploadForm`; unit tests and HTTP CSV/Excel imports |
| Regex email/phone, role code pattern, numeric/string validation, optional text | `ingestion/validators.py`; shared by ingestion, ModelForm, and API serializer |
| Lists/tuples/sets/frozensets/dicts/comprehensions | Row errors/exports, FIELDS tuple, required-column frozenset, skill/duplicate sets, role lookup maps |
| String strip/case/split/join/removeprefix/removesuffix | CandidateValidator, normalize_skills; phone normalization and mailto prefix |
| Indexing/slicing | Phone prefix cleanup uses character indexing and slicing; bounded NLP tokens and ORM result slicing |
| Iterators/while/break/continue | Pandas itertuples → iter_records while/break iterator; process_batch continues past rejected rows before any insert |
| Shallow/deep copy/local/global/nonlocal | rejected_record shallow-copies scalar source fields; CandidateValidator deep-copies nested global validation policy; per-upload nonlocal progress counter |
| Decorator, *args/**kwargs | `timed` service decorator and role-check decorator, wrapped forwarding |
| Recursion/operator overloading | RowValidationError recursively flattens nested field errors for exports; BatchCounts.__add__ combines accepted/rejected outcomes in process_batch |
| Inheritance/lambda/custom exceptions | BaseValidator → CandidateValidator; Django model/view/form inheritance; feature lambda/sorting; InputFileError/RowValidationError |
| Six domain models/relations/constraints/timestamps | `recruitment/models.py`, committed migration; unique candidate email and slot start, FK relations, stage choices |
| Admin columns/filter/search/fieldsets | `recruitment/admin.py`, accounts UserAdmin |
| FBV + CBV/upload/list/detail/edit/delete | `recruitment/views.py`; Django forms/ModelForms; DeleteView confirmation |
| Templates, static, media, optional safety | `templates/`, `static/`, optional resume/image fields, protected downloads |
| AJAX email + dynamic role slots, CSRF | `portal.js`, email_check (POST), role_slots (GET), browser CSRF test |
| Cookie/session | HTTP-only last_role cookie; current_batch session; list filters and reset controls |
| Middleware timing/path/method/role and dashboard gate | `accounts/middleware.py`; login/static/admin/API remain outside dashboard guard |
| PostgreSQL/ORM/migrations | config DB env, migrations, create_database helper; no SQLite fallback |
| get/filter/exclude/order/slice/JSON | batch claims get(), list filters, duplicate validators exclude current record, dashboard/cache slicing; protected JSON views return one candidate or every candidate including rejected rows |
| Required SQL and dashboard aggregates | sql_queries.sql; dashboard displays COUNT/SUM/MIN/MAX/AVG by role and overall; minimum-application filter produces real GROUP BY/HAVING; regression checks capture actual SQL |
| DRF auth/registration/logout/CRUD/upload status/screening/feedback/prediction | `accounts/views.py`, `recruitment/api.py`; validated `openapi.yaml` |
| ModelSerializer + HyperlinkedModelSerializer | CandidateSerializer, FeedbackSerializer, read-only JobRoleSerializer URL |
| HR/Interviewer/Admin and custom permissions | User role model; IsVerified, IsManager, assigned-slot filtering/feedback validation |
| Verification + JWT access/refresh/invalid/expired | hashed OTP with expiry/attempt limit; verified login; rotating/blacklisted refresh; expiry tests |
| Swagger + at least five Postman calls | offline sidecar assets; 14-request Postman collection; Newman/HTTP evidence |
| Celery/Redis progress/failure/cache | process_upload task, process_batch atomic imports, visible progress, safe errors/retry, per-role shortlist cache |
| ML load/clean/missing/duplicates/features/outliers/encode/split/two models/metrics/plot/save/API | `screening/ml.py`, train_ml command; metrics/comparison plot; secured repeatable prediction |
| NLTK tokens/POS/vectors/skill score/blank handling | `screening/nlp.py`, setup_nlp command, secured NLP API; original text retained |
| Executable TensorFlow/Keras ANN | run_ann command; saved/reloaded CPU network and `ann_metrics.json` |
| Repeat calls preserve candidate records | prediction/NLP APIs read only; rescreen updates only derived result; tests and HTTP evidence |
| Submission/README/notes/samples/media/ZIP/viva | README, notes, samples CSV/XLSX/text/PNG, package helper, this map |

The ANN is an executable prototype, as permitted by the rubric. The core Python helpers are now called by the upload/validation workflow; python_concepts.py is a walkthrough of those same helpers. Uploaded binary resumes are optional attachments; resume text is the NLP input. Synthetic ML metrics are mechanics evidence only. See notes.txt for boundaries and platform assumptions.
