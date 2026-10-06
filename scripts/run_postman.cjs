// Execute the v2.1 Postman collection locally; save only non-secret result metadata.
const fs = require('node:fs');
const path = require('node:path');
const newman = require('../.tools/newman/node_modules/newman');
const root = path.resolve(__dirname, '..');
if (!process.env.DEMO_PASSWORD) throw new Error('Set DEMO_PASSWORD first.');
const collection = JSON.parse(fs.readFileSync(path.join(root, 'postman_collection.json'), 'utf8'));
collection.variable.find(variable => variable.key === 'password').value = process.env.DEMO_PASSWORD;
newman.run({
  collection,
  reporters: 'cli', timeoutRequest: 30000,
}, (error, summary) => {
  if (error) throw error;
  const report = {
    runner: 'Postman Newman', checked_at_utc: new Date().toISOString(),
    stats: summary.run.stats,
    failures: summary.run.failures.map(failure => ({name: failure.error.name, message: failure.error.message})),
    requests: summary.run.executions.map(execution => ({name: execution.item.name,
      method: execution.request.method, status: execution.response?.code,
      assertions: execution.assertions?.map(assertion => ({name: assertion.assertion, passed: !assertion.error}))})),
  };
  fs.writeFileSync(path.join(root, 'evidence', 'postman_run.json'), JSON.stringify(report, null, 2));
  process.exitCode = report.failures.length ? 1 : 0;
});
