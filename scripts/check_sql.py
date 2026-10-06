"""Execute all submitted SQL in a read-only PostgreSQL transaction."""
import os
from pathlib import Path
import json
import psycopg
import sqlparse
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
load_dotenv(root / '.env')
report = []
with psycopg.connect(dbname=os.getenv('DB_NAME', 'recruitment_portal'), user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', ''), host=os.getenv('DB_HOST', '127.0.0.1'), port=os.getenv('DB_PORT', '5432')) as connection:
    connection.execute('SET TRANSACTION READ ONLY')
    for number, query in enumerate(sqlparse.split((root / 'sql_queries.sql').read_text(encoding='utf-8')), start=1):
        cursor = connection.execute(query)
        rows = cursor.fetchall()
        report.append({'query': number, 'rows': len(rows), 'passed': True})
        print(f'PASS SQL {number}: {len(rows)} rows')
(root / 'evidence').mkdir(exist_ok=True)
(root / 'evidence' / 'sql_checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
