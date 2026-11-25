const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');
const { fixture, fixtureHash, runtimeRoot, uploadClips, saveProject } = require('./helpers');

test('desktop timeline supports upload, import, pointer, keyboard, effects, audio, and persistence', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'Comprehensive interaction path runs once on desktop Chromium.');
  const originalHashes = ['clip-red.mp4', 'clip-blue.mp4', 'voice.wav', 'music.wav'].map(fixtureHash);
  await page.goto('/');
  await uploadClips(page);

  const initialFirst = await page.locator('.timeline-clip h4').first().textContent();
  const blocks = page.locator('#timeline-video-track .timeline-track-clip');
  await blocks.first().scrollIntoViewIfNeeded();
  const firstBox = await blocks.first().boundingBox();
  const lastBox = await blocks.nth(1).boundingBox();
  await page.mouse.move(firstBox.x + firstBox.width / 2, firstBox.y + firstBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(lastBox.x + lastBox.width - 5, lastBox.y + lastBox.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator('.timeline-clip h4').first()).not.toHaveText(initialFirst);

  await page.locator('#timeline-generated-clips').selectOption('11111111-1111-4111-8111-111111111111');
  await page.locator('#timeline-import-generated').click();
  await expect(page.locator('.timeline-clip')).toHaveCount(3);

  await page.locator('#timeline-zoom').fill('160');
  await expect(page.locator('#timeline-track-canvas')).toHaveCSS('width', /px/);
  const ruler = await page.locator('#timeline-ruler').boundingBox();
  await page.mouse.click(ruler.x + 160, ruler.y + ruler.height / 2);
  await expect(page.locator('#timeline-playhead-time')).toHaveText('00:01.00');

  await page.locator('#timeline-split').click();
  await expect(page.locator('.timeline-clip')).toHaveCount(4);
  await page.locator('#timeline-undo').click();
  await expect(page.locator('.timeline-clip')).toHaveCount(3);
  await page.locator('#timeline-redo').click();
  await expect(page.locator('.timeline-clip')).toHaveCount(4);
  await page.keyboard.press('Control+z');
  await expect(page.locator('.timeline-clip')).toHaveCount(3);
  await page.keyboard.press('Control+y');
  await expect(page.locator('.timeline-clip')).toHaveCount(4);

  await page.getByLabel('Trim start (s)').first().fill('0.10');
  await page.getByLabel('Trim start (s)').first().press('Tab');
  await page.getByLabel('Transition to next').first().selectOption('dissolve');
  await page.getByLabel('Overlay text').first().fill('Milestone 7 overlay');
  await page.getByLabel('Overlay text').first().press('Tab');
  await page.getByLabel('Saturation').first().fill('1.20');
  await page.getByLabel('Saturation').first().press('Tab');

  await page.locator('#timeline-logo-input').setInputFiles(fixture('logo.png'));
  await page.locator('#timeline-upload-logo').click();
  await expect(page.locator('#timeline-logo-name')).toContainText('logo.png');
  await page.locator('#timeline-lut-input').setInputFiles(fixture('identity.cube'));
  await page.locator('#timeline-upload-lut').click();
  await expect(page.locator('#timeline-lut-name')).toContainText('identity.cube');
  await page.getByLabel('Logo overlay', { exact: true }).first().selectOption({ index: 1 });
  await page.getByLabel('Color LUT', { exact: true }).first().selectOption({ index: 1 });

  await page.locator('#timeline-voice-input').setInputFiles(fixture('voice.wav'));
  await expect(page.locator('#timeline-voice-name')).toContainText('voice.wav');
  await page.locator('#timeline-music-input').setInputFiles(fixture('music.wav'));
  await expect(page.locator('#timeline-music-name')).toContainText('music.wav');
  await page.getByLabel('Voice start offset (seconds)').fill('0.25');
  await page.getByLabel('Voice start offset (seconds)').press('Tab');
  await page.getByLabel('Voice sync adjustment (seconds)').fill('0.10');
  await page.getByLabel('Voice sync adjustment (seconds)').press('Tab');
  await page.getByLabel('Voice fade in').fill('0.20');
  await page.getByLabel('Voice fade in').press('Tab');
  await page.getByLabel('Ducking intensity').fill('0.70');

  const projectId = await saveProject(page, 'Milestone 7 persistence');
  await page.reload();
  await page.locator('#timeline-projects').selectOption(projectId);
  await page.locator('#timeline-open-project').click();
  await expect(page.locator('.timeline-clip')).toHaveCount(4);
  await expect(page.getByLabel('Overlay text').first()).toHaveValue('Milestone 7 overlay');
  await expect(page.getByLabel('Transition to next').first()).toHaveValue('dissolve');
  await expect(page.locator('#timeline-voice-name')).toContainText('voice.wav');

  const invalidId = '22222222-2222-4222-8222-222222222222';
  const projectDirectory = path.join(runtimeRoot(), 'project_data', 'timeline_projects');
  fs.writeFileSync(path.join(projectDirectory, `${invalidId}.json`), JSON.stringify({ schema_version: '99.0' }));
  const listed = await page.request.get('/api/timeline/projects');
  expect(listed.ok()).toBeTruthy();
  expect((await listed.json()).warnings.some(warning => warning.includes(invalidId))).toBeTruthy();

  const currentHashes = ['clip-red.mp4', 'clip-blue.mp4', 'voice.wav', 'music.wav'].map(fixtureHash);
  expect(currentHashes).toEqual(originalHashes);
});

test('mobile Chromium sends real touch input for timeline seeking', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-mobile', 'Touch path runs on the emulated mobile Chromium project.');
  await page.goto('/');
  await uploadClips(page);
  await page.locator('#timeline-ruler').scrollIntoViewIfNeeded();
  const ruler = await page.locator('#timeline-ruler').boundingBox();
  await page.touchscreen.tap(ruler.x + Math.min(160, ruler.width - 20), ruler.y + ruler.height / 2);
  await expect(page.locator('#timeline-playhead-time')).not.toHaveText('00:00.00');
});
