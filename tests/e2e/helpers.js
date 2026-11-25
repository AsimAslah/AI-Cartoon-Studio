const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

function runtimeRoot() {
  const root = process.env.AI_CARTOON_E2E_ROOT;
  if (!root) throw new Error('AI_CARTOON_E2E_ROOT is unavailable.');
  return root;
}

function fixture(name) { return path.join(runtimeRoot(), 'fixtures', name); }
function fixtureHash(name) { return crypto.createHash('sha256').update(fs.readFileSync(fixture(name))).digest('hex'); }

function ffprobe(file) {
  return JSON.parse(execFileSync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,r_frame_rate',
    '-of', 'json', file,
  ], { encoding: 'utf8' }));
}

async function uploadClips(page, names = ['clip-red.mp4', 'clip-blue.mp4']) {
  await page.locator('#timeline-clip-input').setInputFiles(names.map(fixture));
  await page.locator('#timeline-upload-clips').click();
  await page.locator('.timeline-clip').nth(names.length - 1).waitFor();
}

async function saveProject(page, name = 'Milestone 7 project') {
  await page.locator('#timeline-project-name').fill(name);
  await page.locator('#timeline-save-project').click();
  await page.locator('#timeline-message').filter({ hasText: `Saved ${name}` }).waitFor();
  return page.locator('#timeline-projects').inputValue();
}

async function waitForExport(page, timeout = 90_000) {
  await page.locator('#timeline-export-state.completed').waitFor({ timeout });
  const href = await page.locator('#timeline-export-download').getAttribute('href');
  if (!href) throw new Error('Completed export did not expose an output URL.');
  return href;
}

module.exports = { runtimeRoot, fixture, fixtureHash, ffprobe, uploadClips, saveProject, waitForExport };
