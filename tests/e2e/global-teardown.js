const fs = require('fs');
const os = require('os');
const path = require('path');

module.exports = async () => {
  const root = process.env.AI_CARTOON_E2E_ROOT;
  const cleanupToken = process.env.AI_CARTOON_E2E_TOKEN;
  if (!root || process.env.AI_CARTOON_E2E_KEEP_RUNTIME === '1') return;
  const resolvedRoot = path.resolve(root);
  const safeParent = path.resolve(os.tmpdir());
  const marker = path.join(resolvedRoot, '.e2e-cleanup-token');
  const safeName = path.basename(resolvedRoot).startsWith('ai-cartoon-studio-e2e-');
  const safeLocation = path.dirname(resolvedRoot).toLowerCase() === safeParent.toLowerCase();
  const safeMarker = cleanupToken && fs.existsSync(marker) && fs.readFileSync(marker, 'utf8') === cleanupToken;
  if (!safeName || !safeLocation || !safeMarker) {
    throw new Error('Refusing to clean an unverified E2E runtime directory.');
  }
  try {
    fs.rmSync(resolvedRoot, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  } catch (error) {
    console.warn(`E2E runtime cleanup was blocked: ${error.message}`);
  }
};
