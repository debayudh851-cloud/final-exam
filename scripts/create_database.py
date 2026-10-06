"""Create only the configured project database; never alters existing databases."""
import os
from pathlib import Path
import psycopg
from psycopg import sql
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')
name = os.getenv('DB_NAME', 'recruitment_portal')
with psycopg.connect(dbname='postgres', user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', ''), host=os.getenv('DB_HOST', '127.0.0.1'),
    port=os.getenv('DB_PORT', '5432'), autocommit=True) as conn:
    if conn.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name]).fetchone():
        print('Project database already exists.')
    else:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        print('Created project database.')
