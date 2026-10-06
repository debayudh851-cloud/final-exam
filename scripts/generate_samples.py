"""Generate reproducible synthetic fixtures; no real candidate information."""
from pathlib import Path
import csv
import random
import pandas as pd
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent.parent
folder = root / 'samples'
folder.mkdir(exist_ok=True)
rng = random.Random(42)
rows = []
for i in range(240):
    role = 'Python Developer' if i % 2 == 0 else 'Django Developer'
    experience = rng.randint(0, 36)
    notice = rng.choice([0, 15, 30, 60, 90])
    salary = rng.randint(250, 1100) * 1000
    skills = rng.choice(['python, django, postgresql, git, rest', 'python, sql, git', 'html, css', 'python, django'])
    selected = (experience >= 6 and notice <= 60 and salary <= 800000 and 'python' in skills)
    if rng.random() < .12:
        selected = not selected
    rows.append({'candidate_name': f'Demo Candidate {i + 1:03d}', 'email': f'candidate{i + 1}@example.test',
        'phone': str(9100000000 + i), 'college': f'Demo College {i % 5 + 1}', 'applied_role': role,
        'skills': skills, 'experience_months': experience, 'notice_period_days': notice, 'expected_salary': salary,
        'resume_text': f'I build applications with {skills}. I enjoy learning and collaborating on software.',
        'portfolio_url': '', 'historical_selection_status': 'SELECTED' if selected else 'REJECTED'})
pd.DataFrame(rows).to_csv(folder / 'training.csv', index=False)
small = [dict(row) for row in rows[:12]]
small.append(dict(small[0]))
small.append({**rows[13], 'email': 'invalid-email', 'phone': '123', 'expected_salary': '-10', 'experience_months': 'six'})
small.append({**rows[14], 'applied_role': 'Unknown Role'})
small.append({**rows[15], 'email': 'optional@example.test', 'resume_text': '', 'portfolio_url': ''})
pd.DataFrame(small).to_csv(folder / 'candidates.csv', index=False)
pd.DataFrame(small).to_excel(folder / 'candidates.xlsx', index=False)
pd.DataFrame(rows[30:150]).to_csv(folder / 'large_batch.csv', index=False)
(folder / 'resume.txt').write_text('Demo resume: Python, Django, PostgreSQL, SQL, REST, Git. Campus project experience.', encoding='utf-8')
image = Image.new('RGB', (160, 160), '#e8f0ff')
draw = ImageDraw.Draw(image)
draw.ellipse((51, 24, 109, 82), fill='#7299da')
draw.rounded_rectangle((27, 89, 133, 160), radius=34, fill='#7299da')
image.save(folder / 'candidate.png')
print('Generated synthetic CSV, Excel, large batch, resume, and image fixtures.')
