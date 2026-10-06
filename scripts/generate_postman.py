from pathlib import Path
import json

root = Path(__file__).resolve().parent.parent
items = []


def add(name, method, path, status, body=None, authenticated=True, extra_tests=None):
    headers = [{'key': 'Authorization', 'value': 'Bearer {{access}}'}] if authenticated else []
    request = {'method': method, 'header': headers, 'url': '{{base_url}}' + path}
    if body is not None:
        headers.append({'key': 'Content-Type', 'value': 'application/json'})
        request['body'] = {'mode': 'raw', 'raw': json.dumps(body), 'options': {'raw': {'language': 'json'}}}
    tests = [f'pm.test("Status is {status}", function () {{ pm.response.to.have.status({status}); }});']
    tests.extend(extra_tests or [])
    items.append({'name': name, 'request': request, 'event': [{'listen': 'test', 'script': {'type': 'text/javascript', 'exec': tests}}]})


add('01 Unauthenticated access denied', 'GET', '/api/candidates/', 401, authenticated=False)
add('02 Login as HR', 'POST', '/api/auth/login/', 200, {'username': 'hr', 'password': '{{password}}'}, False,
    ['const loginPayload = pm.response.json(); pm.collectionVariables.set("access", loginPayload.access); pm.collectionVariables.set("refresh", loginPayload.refresh);',
     'pm.collectionVariables.set("run_id", Date.now().toString());'])
add('03 List hyperlinked roles', 'GET', '/api/roles/', 200, extra_tests=[
    'const roles = pm.response.json().results; pm.expect(roles.length).to.be.above(0); pm.collectionVariables.set("role_id", roles[0].id); pm.collectionVariables.set("role_name", roles[0].name);'])
payload = {'candidate_name': 'Postman Demo', 'email': 'postman.{{run_id}}@example.test', 'phone': '9876543210',
    'college': 'Demo College', 'applied_role': '{{role_id}}', 'skills': 'python, django, sql',
    'experience_months': 12, 'notice_period_days': 30, 'expected_salary': '500000.00',
    'resume_text': 'I build Python and Django applications with SQL and Git.', 'portfolio_url': '', 'historical_selection_status': 'SELECTED'}
add('04 Create synthetic candidate', 'POST', '/api/candidates/', 201, payload, extra_tests=[
    'pm.collectionVariables.set("candidate_id", pm.response.json().id);'])
add('05 Retrieve candidate', 'GET', '/api/candidates/{{candidate_id}}/', 200)
add('06 PUT candidate', 'PUT', '/api/candidates/{{candidate_id}}/', 200, {**payload, 'college': 'Updated Demo College'})
add('07 PATCH screening stage', 'PATCH', '/api/candidates/{{candidate_id}}/', 200, {'status': 'SHORTLISTED'})
add('08 Invalid number rejected', 'PATCH', '/api/candidates/{{candidate_id}}/', 400, {'experience_months': -1})
add('09 Secured ML prediction', 'POST', '/api/screening/predict/', 200, {
    'experience_months': 12, 'notice_period_days': 30, 'expected_salary': 500000, 'skills': 'python, django, sql', 'applied_role': '{{role_name}}'},
    extra_tests=['pm.expect(pm.response.json().probability).to.be.within(0, 1);'])
add('10 NLTK resume analysis', 'POST', '/api/screening/nlp/', 200, {'resume_text': 'Python Django PostgreSQL SQL Git', 'role': '{{role_id}}'},
    extra_tests=['pm.expect(pm.response.json().pos_tags.length).to.be.above(0);'])
add('11 Screening results', 'GET', '/api/screening-results/', 200)
add('12 Delete synthetic API record', 'DELETE', '/api/candidates/{{candidate_id}}/', 204)
add('13 Logout refresh token', 'POST', '/api/auth/logout/', 200, {'refresh': '{{refresh}}'})
add('14 Revoked refresh denied', 'POST', '/api/auth/refresh/', 401, {'refresh': '{{refresh}}'}, False)
collection = {'info': {'name': 'TalentDesk Assessment API', 'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},
    'variable': [{'key': 'base_url', 'value': 'http://127.0.0.1:8000'}, {'key': 'password', 'value': ''},
                 {'key': 'access', 'value': ''}, {'key': 'refresh', 'value': ''}], 'item': items}
(root / 'postman_collection.json').write_text(json.dumps(collection, indent=2), encoding='utf-8')
print('Generated 14-request Postman collection with assertions.')
