"""Package source and non-secret demonstration artifacts with an explicit allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from dotenv import dotenv_values

root = Path(__file__).resolve().parent.parent
directories = ['config', 'accounts', 'recruitment', 'ingestion', 'screening', 'templates', 'static', 'samples', 'scripts', 'evidence']
files = ['manage.py', 'README.md', 'README.md.md', 'notes.txt', 'coverage.md', 'sql_queries.sql',
         'requirements.txt', 'requirements-lock.txt', '.env.example', '.gitignore', 'postman_collection.json', 'openapi.yaml']
artifact_files = ['shortlist.joblib', 'ann.keras', 'ann_preprocessor.joblib', 'ml_metrics.json', 'ann_metrics.json', 'model_comparison.png']
paths = [root / file for file in files]
paths.extend(root / 'artifacts' / file for file in artifact_files)
for directory in directories:
    paths.extend(path for path in (root / directory).rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
with ZipFile(root / 'recruitment_portal_submission.zip', 'w', ZIP_DEFLATED) as archive:
    for path in sorted(set(paths)):
        if not path.exists():
            raise FileNotFoundError(path.name)
        archive.write(path, Path('recruitment_portal') / path.relative_to(root))
with ZipFile(root / 'recruitment_portal_submission.zip') as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert not any(name.endswith('/.env') or '/.venv/' in name or '/media/' in name for name in names)
    password = dotenv_values(root / '.env').get('DB_PASSWORD')
    if password:
        assert not any(password.encode() in archive.read(name) for name in names), 'Database secret found in submission.'
print(f'Created and verified ZIP with {len(names)} files. Local secrets and uploads excluded.')
