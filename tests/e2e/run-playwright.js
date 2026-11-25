const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const runtimeRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-cartoon-studio-e2e-'));
const cleanupToken = crypto.randomUUID();
fs.writeFileSync(path.join(runtimeRoot, '.e2e-cleanup-token'), cleanupToken, { encoding: 'utf8', flag: 'wx' });
const playwrightCli = require.resolve('@playwright/test/cli');
const completed = spawnSync(process.execPath, [playwrightCli, 'test', ...process.argv.slice(2)], {
  cwd: path.resolve(__dirname, '..', '..'),
  env: { ...process.env, AI_CARTOON_E2E_ROOT: runtimeRoot, AI_CARTOON_E2E_TOKEN: cleanupToken },
  stdio: 'inherit',
  shell: false,
});
if (completed.error) throw completed.error;
process.exitCode = completed.status ?? 1;
