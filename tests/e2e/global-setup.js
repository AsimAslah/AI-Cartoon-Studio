const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

function ffmpeg(args) {
  execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args], { stdio: 'inherit' });
}

module.exports = async () => {
  const root = process.env.AI_CARTOON_E2E_ROOT;
  const cleanupToken = process.env.AI_CARTOON_E2E_TOKEN;
  if (!root || !cleanupToken) throw new Error('The isolated E2E runtime was not configured by the test wrapper.');
  const marker = path.join(root, '.e2e-cleanup-token');
  if (fs.readFileSync(marker, 'utf8') !== cleanupToken) throw new Error('The E2E runtime cleanup marker is invalid.');
  const fixtures = path.join(root, 'fixtures');
  fs.mkdirSync(fixtures, { recursive: true });

  const makeClip = (name, color, frequency, duration) => ffmpeg([
    '-f', 'lavfi', '-i', `color=c=${color}:s=320x180:r=30:d=${duration}`,
    '-f', 'lavfi', '-i', `sine=frequency=${frequency}:sample_rate=48000:duration=${duration}`,
    '-shortest', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', path.join(fixtures, name),
  ]);
  makeClip('clip-red.mp4', 'red', 440, 2);
  makeClip('clip-blue.mp4', 'blue', 660, 2.4);
  ffmpeg(['-f', 'lavfi', '-i', 'sine=frequency=330:sample_rate=48000:duration=3', '-c:a', 'pcm_s16le', path.join(fixtures, 'voice.wav')]);
  ffmpeg(['-f', 'lavfi', '-i', 'sine=frequency=110:sample_rate=48000:duration=4', '-c:a', 'pcm_s16le', path.join(fixtures, 'music.wav')]);
  ffmpeg(['-f', 'lavfi', '-i', 'color=c=green:s=320x180', '-frames:v', '1', path.join(fixtures, 'still.png')]);
  ffmpeg(['-f', 'lavfi', '-i', 'color=c=white:s=128x64', '-frames:v', '1', path.join(fixtures, 'logo.png')]);
  fs.writeFileSync(path.join(fixtures, 'identity.cube'), [
    'TITLE "Identity"', 'LUT_3D_SIZE 2',
    '0 0 0', '0 0 1', '0 1 0', '0 1 1', '1 0 0', '1 0 1', '1 1 0', '1 1 1', '',
  ].join('\n'), 'utf8');

  const generatedId = '11111111-1111-4111-8111-111111111111';
  const generatedDir = path.join(root, 'output', 'video_generation_jobs', generatedId);
  fs.mkdirSync(generatedDir, { recursive: true });
  fs.copyFileSync(path.join(fixtures, 'clip-blue.mp4'), path.join(generatedDir, 'generated.mp4'));
  fs.writeFileSync(path.join(root, 'fixture-manifest.json'), JSON.stringify({ generatedId }, null, 2));
};
