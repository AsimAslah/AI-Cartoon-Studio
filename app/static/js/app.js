const storyText = document.querySelector('#story-text');
const message = document.querySelector('#message');
const storyboard = document.querySelector('#storyboard');
const storyboardButton = document.querySelector('#storyboard-button');
const renderButton = document.querySelector('#render-button');

function say(text, error = false) {
  message.textContent = text;
  message.className = error ? 'error' : '';
}

async function jsonOrError(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Request failed.');
  return data;
}

fetch('/api/capabilities').then(jsonOrError).then(data => {
  const status = document.querySelector('#blender-status');
  status.textContent = data.blender_available ? '● Blender ready' : '○ Blender not found';
});

document.querySelector('#story-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  say(`Extracting ${file.name}…`);
  const form = new FormData();
  form.append('file', file);
  try {
    const data = await jsonOrError(await fetch('/api/extract', {method: 'POST', body: form}));
    storyText.value = data.text;
    say(`Loaded ${data.filename}. Review the text, then generate the storyboard.`);
  } catch (error) { say(error.message, true); }
});

storyboardButton.addEventListener('click', async () => {
  storyboardButton.disabled = true;
  say('Analyzing supported story elements…');
  try {
    const data = await jsonOrError(await fetch('/api/storyboard', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: storyText.value})}));
    document.querySelector('#scene-count').textContent = `${data.scenes.length} scenes`;
    document.querySelector('#warnings').innerHTML = data.global_warnings.map(w => `<p class="warning">${escapeHtml(w)}</p>`).join('');
    storyboard.className = '';
    storyboard.innerHTML = data.scenes.map(scene => `<section class="scene"><h3>Scene ${scene.scene_id} · ${scene.action.replace('_', ' ')}</h3><p>${escapeHtml(scene.narration)}</p><p>Forest · Fox · ${scene.duration_seconds}s · ${scene.mood}</p>${scene.warnings.map(w => `<p class="warning">${escapeHtml(w)}</p>`).join('')}</section>`).join('');
    say('Storyboard generated. You can edit the story and regenerate it.');
  } catch (error) { say(error.message, true); }
  finally { storyboardButton.disabled = false; }
});

renderButton.addEventListener('click', async () => {
  renderButton.disabled = true;
  say('Blender is rendering a real 3D preview. This may take a minute…');
  try {
    const data = await jsonOrError(await fetch('/api/render/demo?preview_only=true', {method: 'POST'}));
    const preview = document.querySelector('#preview');
    preview.classList.remove('hidden');
    preview.querySelector('img').src = `/api/output/preview.png?t=${Date.now()}`;
    say(`Render completed in ${data.duration_seconds} seconds.`);
  } catch (error) { say(error.message, true); }
  finally { renderButton.disabled = false; }
});

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value;
  return div.innerHTML;
}
