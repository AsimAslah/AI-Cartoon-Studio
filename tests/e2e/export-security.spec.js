const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');
const { fixture, fixtureHash, ffprobe, runtimeRoot, uploadClips, saveProject, waitForExport } = require('./helpers');

async function downloadAndProbe(page, href, name) {
  const response = await page.request.get(href);
  expect(response.ok()).toBeTruthy();
  const destination = path.join(runtimeRoot(), 'downloads', name);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, await response.body());
  return { destination, metadata: ffprobe(destination) };
}

test('approximate preview and real rendered 720p/1080p exports validate with FFprobe', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'Real CPU export path runs once on desktop Chromium.');
  const before = ['clip-red.mp4', 'clip-blue.mp4', 'voice.wav', 'music.wav'].map(fixtureHash);
  await page.goto('/');
  await uploadClips(page);
  await page.locator('#timeline-voice-input').setInputFiles(fixture('voice.wav'));
  await expect(page.locator('#timeline-voice-name')).toContainText('voice.wav');
  await page.locator('#timeline-music-input').setInputFiles(fixture('music.wav'));
  await expect(page.locator('#timeline-music-name')).toContainText('music.wav');
  await saveProject(page, 'Milestone 7 export verification');

  await page.locator('.timeline-clip').first().getByRole('button', { name: 'Preview' }).click();
  await expect(page.locator('#timeline-preview')).not.toHaveClass(/hidden/);

  await page.locator('#timeline-render-preview').click();
  const previewHref = await waitForExport(page);
  const preview = await downloadAndProbe(page, previewHref, 'rendered-preview-720p.mp4');
  const previewVideo = preview.metadata.streams.find(stream => stream.codec_type === 'video');
  const previewAudio = preview.metadata.streams.find(stream => stream.codec_type === 'audio');
  expect([previewVideo.width, previewVideo.height, previewVideo.codec_name]).toEqual([1280, 720, 'h264']);
  expect(previewVideo.r_frame_rate).toBe('30/1');
  expect(previewAudio.codec_name).toBe('aac');
  expect(Number(preview.metadata.format.duration)).toBeGreaterThan(4.2);
  expect(Number(preview.metadata.format.duration)).toBeLessThan(4.6);

  await page.getByLabel('Export profile').selectOption('1080p');
  await page.locator('#timeline-export').click();
  await expect(page.locator('#timeline-export-state')).not.toHaveClass(/completed/);
  const exportHref = await waitForExport(page);
  const exported = await downloadAndProbe(page, exportHref, 'timeline-1080p.mp4');
  const exportVideo = exported.metadata.streams.find(stream => stream.codec_type === 'video');
  const exportAudio = exported.metadata.streams.find(stream => stream.codec_type === 'audio');
  expect([exportVideo.width, exportVideo.height, exportVideo.codec_name]).toEqual([1920, 1080, 'h264']);
  expect(exportVideo.r_frame_rate).toBe('30/1');
  expect(exportAudio.codec_name).toBe('aac');
  expect(Number(exported.metadata.format.duration)).toBeGreaterThan(4.2);
  expect(Number(exported.metadata.format.duration)).toBeLessThan(4.6);

  const jobId = exportHref.split('/').at(-2);
  const jobDirectory = path.join(runtimeRoot(), 'output', 'timeline_exports', jobId);
  expect(fs.readdirSync(jobDirectory).sort()).toEqual(['timeline-export.mp4']);
  expect(['clip-red.mp4', 'clip-blue.mp4', 'voice.wav', 'music.wav'].map(fixtureHash)).toEqual(before);
});

test('upload validation, command arguments, traversal, size limits, and remote consent are enforced', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'Security integration path runs once on desktop Chromium.');
  await page.goto('/');

  const invalid = await page.request.post('/api/timeline/media', { multipart: {
    kind: 'clip', media: { name: 'invalid.mp4', mimeType: 'video/mp4', buffer: Buffer.from('not an mp4') },
  } });
  expect(invalid.status()).toBe(422);

  const oversized = await page.request.post('/api/timeline/media', { multipart: {
    kind: 'lut', media: { name: 'oversized.cube', mimeType: 'text/plain', buffer: Buffer.alloc(5 * 1024 * 1024 + 1, 65) },
  } });
  expect(oversized.status()).toBe(422);

  const injectedName = 'clip;echo-owned.mp4';
  const injection = await page.request.post('/api/timeline/media', { multipart: {
    kind: 'clip', media: { name: injectedName, mimeType: 'video/mp4', buffer: fs.readFileSync(fixture('clip-red.mp4')) },
  } });
  expect(injection.status()).toBe(201);
  const injectionPayload = await injection.json();
  expect(injectionPayload.original_filename).toBe(injectedName);
  expect(injectionPayload.stored_filename).toBe('source.mp4');
  expect(fs.existsSync(path.join(runtimeRoot(), 'owned'))).toBeFalsy();

  const traversal = await page.request.get('/api/timeline/media/%2e%2e%2foutside');
  expect([404, 422]).toContain(traversal.status());

  const remote = await page.request.post('/api/video/jobs', { data: {
    upload_id: '00000000-0000-0000-0000-000000000000',
    provider_id: 'huggingface_ltx_2_5',
    prompt: 'A deterministic request that must never be submitted.',
    remote_processing_consent: false,
    settings: { duration_seconds: 1, width: 1024, height: 576 },
  } });
  expect(remote.status()).toBe(422);
});
