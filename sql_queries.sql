-- PostgreSQL 18 / Django-generated recruitment_* schema. All examples are read-only.
-- 1. Candidate search, WHERE, AND/OR, ORDER BY, LIMIT.
SELECT id, candidate_name, email, status FROM recruitment_candidate
WHERE (candidate_name ILIKE '%demo%' OR email ILIKE '%example.test%')
AND status <> 'REJECTED' ORDER BY candidate_name LIMIT 20;

-- 2. Role-wise counts, including roles with no candidates.
SELECT r.name, COUNT(c.id) AS candidate_count FROM recruitment_jobrole r
LEFT JOIN recruitment_candidate c ON c.applied_role_id = r.id GROUP BY r.id, r.name ORDER BY candidate_count DESC;

-- 3. Selected/rejected aggregation.
SELECT status, COUNT(*) AS total FROM recruitment_candidate
WHERE status IN ('SELECTED', 'REJECTED') GROUP BY status;

-- 4. Salary BETWEEN.
SELECT candidate_name, expected_salary FROM recruitment_candidate
WHERE expected_salary BETWEEN 300000 AND 800000 ORDER BY expected_salary;

-- 5. Skills LIKE; skills are normalized to lowercase by ingestion/API/forms.
SELECT id, candidate_name, skills FROM recruitment_candidate WHERE skills LIKE '%python%';

-- 6. INNER JOIN.
SELECT c.candidate_name, r.name AS role FROM recruitment_candidate c
INNER JOIN recruitment_jobrole r ON c.applied_role_id = r.id;

-- 7. FULL OUTER JOIN: FK prevents orphan candidates, but empty roles still appear.
SELECT r.name, c.candidate_name FROM recruitment_jobrole r
FULL OUTER JOIN recruitment_candidate c ON c.applied_role_id = r.id ORDER BY r.name;

-- 8. Never NATURAL JOIN base tables: shared id columns have different meanings.
-- Project each side so applied_role_id is the ONLY shared name; then natural join is safe.
SELECT candidate_name, role_name FROM
(SELECT candidate_name, applied_role_id FROM recruitment_candidate) c
NATURAL JOIN (SELECT id AS applied_role_id, name AS role_name FROM recruitment_jobrole) r;
-- Safe explicit equivalent:
SELECT c.candidate_name, r.name AS role_name FROM recruitment_candidate c
JOIN recruitment_jobrole r ON c.applied_role_id = r.id;

-- 9. UNION ALL.
SELECT id, candidate_name, status FROM recruitment_candidate WHERE status = 'SELECTED'
UNION ALL
SELECT id, candidate_name, status FROM recruitment_candidate WHERE status = 'WAITLISTED';

-- 10. INTERSECT.
SELECT id, candidate_name FROM recruitment_candidate WHERE skills LIKE '%python%'
INTERSECT
SELECT id, candidate_name FROM recruitment_candidate WHERE skills LIKE '%django%';

-- 11. Dashboard COUNT, SUM, MIN, MAX, AVG, GROUP BY, HAVING.
SELECT r.name, COUNT(c.id) AS total, SUM(c.expected_salary) AS salary_sum,
MIN(c.expected_salary) AS salary_min, MAX(c.expected_salary) AS salary_max,
AVG(c.expected_salary) AS salary_avg FROM recruitment_jobrole r
JOIN recruitment_candidate c ON c.applied_role_id = r.id
GROUP BY r.id, r.name HAVING COUNT(c.id) > 0 ORDER BY total DESC;
