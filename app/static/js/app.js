const storyText = document.querySelector('#story-text');
const storyboardRoot = document.querySelector('#storyboard');
const message = document.querySelector('#message');
const validationMessage = document.querySelector('#validation-message');
const projectName = document.querySelector('#project-name');
const projectId = document.querySelector('#project-id');
const saveMessage = document.querySelector('#save-message');

const state = {scenes: [], renderTimer: null};
const actions = ['idle', 'walk', 'turn', 'approach', 'look', 'touch'];

function say(text, kind = 'notice', target = message) {
  target.textContent = text;
  target.className = text ? kind : '';
}

async function jsonOrError(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : formatValidation(data.detail) || 'Request failed.';
    throw new Error(detail);
  }
  return data;
}

function formatValidation(detail) {
  if (!Array.isArray(detail)) return detail?.message || '';
  return detail.map(item => `${item.loc?.slice(1).join(' → ') || 'field'}: ${item.msg}`).join('; ');
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value ?? '';
  return div.innerHTML;
}

function normalizeOrders() {
  state.scenes.forEach((scene, index) => { scene.order = index; });
}

function storyboardDocument() {
  normalizeOrders();
  return {schema_version: '1.0', title: projectName.value.trim() || 'Untitled storyboard', scenes: state.scenes};
}

function renderScenes() {
  document.querySelector('#scene-count').textContent = `${state.scenes.length} scene${state.scenes.length === 1 ? '' : 's'}`;
  if (!state.scenes.length) {
    storyboardRoot.className = 'empty';
    storyboardRoot.textContent = 'Generate a storyboard or add a scene to begin.';
    return;
  }
  storyboardRoot.className = '';
  storyboardRoot.innerHTML = state.scenes.map((scene, index) => `
    <article class="scene-card" data-index="${index}">
      <div class="scene-header">
        <h3>Scene ${index + 1} <span class="muted">#${scene.scene_id}</span></h3>
        <div class="scene-actions">
          <button type="button" data-command="up" aria-label="Move scene up" ${index === 0 ? 'disabled' : ''}>↑</button>
          <button type="button" data-command="down" aria-label="Move scene down" ${index === state.scenes.length - 1 ? 'disabled' : ''}>↓</button>
          <button type="button" data-command="delete" class="delete" aria-label="Delete scene">Delete</button>
        </div>
      </div>
      <div class="scene-grid">
        <div class="wide"><label>Description</label><input data-field="description" maxlength="500"></div>
        <div><label>Environment</label><select data-field="environment"><option value="magical_forest">Magical forest</option></select></div>
        <div><label>Character</label><select data-field="character"><option value="fox">Fox</option></select></div>
        <div><label>Action</label><select data-field="action">${actions.map(action => `<option value="${action}" ${scene.action === action ? 'selected' : ''}>${action}</option>`).join('')}</select></div>
        <div><label>Duration (seconds)</label><input data-field="duration_seconds" type="number" min="1" max="30" value="${scene.duration_seconds}"></div>
        <div class="wide"><label>Narration</label><textarea data-field="narration" rows="2" maxlength="2000">${escapeHtml(scene.narration)}</textarea></div>
        <div class="wide"><label>Dialogue (optional)</label><textarea data-field="dialogue" rows="2" maxlength="1000">${escapeHtml(scene.dialogue || '')}</textarea></div>
      </div>
    </article>`).join('');
  storyboardRoot.querySelectorAll('.scene-card').forEach((card, index) => {
    card.querySelector('[data-field="description"]').value = state.scenes[index].description;
  });
}

function addScene() {
  const nextId = state.scenes.reduce((maximum, scene) => Math.max(maximum, Number(scene.scene_id) || 0), 0) + 1;
  state.scenes.push({scene_id: nextId, order: state.scenes.length, description: 'The fox pauses in the magical forest.', environment: 'magical_forest', characters: ['fox'], action: 'idle', narration: 'The fox pauses in the magical forest.', dialogue: null, mood: 'wonder', duration_seconds: 4, warnings: []});
  renderScenes();
}

storyboardRoot.addEventListener('input', event => {
  const card = event.target.closest('.scene-card');
  if (!card) return;
  const scene = state.scenes[Number(card.dataset.index)];
  const field = event.target.dataset.field;
  if (!field) return;
  if (field === 'character') scene.characters = [event.target.value];
  else if (field === 'duration_seconds') scene[field] = Number(event.target.value);
  else scene[field] = event.target.value || (field === 'dialogue' ? null : '');
});

storyboardRoot.addEventListener('click', event => {
  const button = event.target.closest('button[data-command]');
  if (!button) return;
  const index = Number(button.closest('.scene-card').dataset.index);
  if (button.dataset.command === 'delete') state.scenes.splice(index, 1);
  if (button.dataset.command === 'up' && index > 0) [state.scenes[index - 1], state.scenes[index]] = [state.scenes[index], state.scenes[index - 1]];
  if (button.dataset.command === 'down' && index < state.scenes.length - 1) [state.scenes[index + 1], state.scenes[index]] = [state.scenes[index], state.scenes[index + 1]];
  normalizeOrders();
  renderScenes();
});

async function validateStoryboard() {
  const data = await jsonOrError(await fetch('/api/storyboard/validate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(storyboardDocument())}));
  state.scenes = data.storyboard.scenes;
  renderScenes();
  say(data.warnings.length ? `Valid with limitations: ${data.warnings.join(' ')}` : 'Storyboard is valid.', data.warnings.length ? 'warning' : 'success', validationMessage);
  return data.storyboard;
}

document.querySelector('#storyboard-button').addEventListener('click', async event => {
  event.target.disabled = true;
  say('Analyzing supported story elements…');
  try {
    const data = await jsonOrError(await fetch('/api/storyboard', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: storyText.value})}));
    state.scenes = data.scenes;
    renderScenes();
    const warnings = [...data.global_warnings, ...data.scenes.flatMap(scene => scene.warnings || [])];
    say(warnings.length ? warnings.join(' ') : 'Storyboard generated. Review and edit every scene.', warnings.length ? 'warning' : 'success');
  } catch (error) { say(error.message, 'error'); }
  finally { event.target.disabled = false; }
});

document.querySelector('#story-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  const form = new FormData(); form.append('file', file);
  say(`Extracting ${file.name}…`);
  try {
    const data = await jsonOrError(await fetch('/api/extract', {method: 'POST', body: form}));
    storyText.value = data.text;
    say(`Loaded ${data.filename}. Review the text before generating scenes.`, 'success');
  } catch (error) { say(error.message, 'error'); }
});

document.querySelector('#add-scene-button').addEventListener('click', addScene);
document.querySelector('#validate-button').addEventListener('click', async () => {
  try { await validateStoryboard(); } catch (error) { say(error.message, 'error', validationMessage); }
});

async function saveProject() {
  const storyboard = await validateStoryboard();
  const payload = {name: projectName.value, story_text: storyText.value, storyboard};
  const id = projectId.value;
  const response = await fetch(id ? `/api/projects/${id}` : '/api/projects', {method: id ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  const saved = await jsonOrError(response);
  projectId.value = saved.project_id;
  say(`Saved “${saved.name}” at ${new Date(saved.updated_at).toLocaleTimeString()}.`, 'success', saveMessage);
  await loadProjectList();
}

document.querySelector('#save-button').addEventListener('click', async event => {
  event.target.disabled = true;
  try { await saveProject(); } catch (error) { say(error.message, 'error', saveMessage); }
  finally { event.target.disabled = false; }
});

document.querySelector('#new-button').addEventListener('click', () => {
  projectId.value = '';
  projectName.value = `${projectName.value || 'Untitled'} copy`;
  say('This copy will receive a new project ID when saved.', 'notice', saveMessage);
});

async function loadProjectList() {
  const root = document.querySelector('#project-list');
  try {
    const data = await jsonOrError(await fetch('/api/projects'));
    root.innerHTML = data.projects.length ? data.projects.map(project => `<div class="project-item"><div><strong>${escapeHtml(project.name)}</strong><small>${project.scene_count} scene(s) · ${new Date(project.updated_at).toLocaleString()}</small></div><button type="button" data-project-id="${project.project_id}">Open</button></div>`).join('') : '<p class="muted">No saved projects yet.</p>';
    if (data.warnings.length) say(data.warnings.join(' '), 'warning', saveMessage);
  } catch (error) { root.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`; }
}

document.querySelector('#project-list').addEventListener('click', async event => {
  const button = event.target.closest('button[data-project-id]');
  if (!button) return;
  try {
    const project = await jsonOrError(await fetch(`/api/projects/${button.dataset.projectId}`));
    projectId.value = project.project_id; projectName.value = project.name; storyText.value = project.story_text; state.scenes = project.storyboard.scenes;
    renderScenes(); say(`Opened “${project.name}”.`, 'success', saveMessage);
  } catch (error) { say(error.message, 'error', saveMessage); }
});

document.querySelector('#refresh-projects').addEventListener('click', loadProjectList);

function showRender(job) {
  const root = document.querySelector('#render-state');
  root.className = `render-state ${job.state.toLowerCase()}`;
  root.innerHTML = `<strong>${escapeHtml(job.state)}</strong><span>${escapeHtml(job.message)}</span>${job.error ? `<span class="error">${escapeHtml(job.error)}</span>` : ''}`;
}

async function pollRender(jobId) {
  clearTimeout(state.renderTimer);
  try {
    const job = await jsonOrError(await fetch(`/api/renders/${jobId}`));
    showRender(job);
    if (job.state === 'COMPLETED') {
      const url = `/api/renders/${jobId}/output`;
      document.querySelector('#rendered-video').src = url;
      document.querySelector('#download-link').href = url;
      document.querySelector('#video-preview').classList.remove('hidden');
      document.querySelector('#render-button').disabled = false;
    } else if (job.state === 'FAILED') document.querySelector('#render-button').disabled = false;
    else state.renderTimer = setTimeout(() => pollRender(jobId), 1200);
  } catch (error) { say(error.message, 'error'); document.querySelector('#render-button').disabled = false; }
}

document.querySelector('#render-button').addEventListener('click', async event => {
  event.target.disabled = true;
  document.querySelector('#video-preview').classList.add('hidden');
  try {
    const storyboard = await validateStoryboard();
    const job = await jsonOrError(await fetch('/api/renders', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({storyboard})}));
    showRender(job); pollRender(job.job_id);
  } catch (error) { say(error.message, 'error'); event.target.disabled = false; }
});

fetch('/api/capabilities').then(jsonOrError).then(data => {
  document.querySelector('#blender-status').textContent = data.blender_available ? '● Blender ready' : '○ Blender unavailable';
}).catch(error => say(error.message, 'error'));

addScene();
loadProjectList();
