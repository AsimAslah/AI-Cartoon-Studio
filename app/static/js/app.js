const storyText = document.querySelector('#story-text');
const storyboardRoot = document.querySelector('#storyboard');
const message = document.querySelector('#message');
const validationMessage = document.querySelector('#validation-message');
const projectName = document.querySelector('#project-name');
const projectId = document.querySelector('#project-id');
const saveMessage = document.querySelector('#save-message');

const state = {scenes: [], renderTimer: null, lipsyncTimer: null, lipsyncUploadId: null, lipsyncProviders: [], videoUploadId: null, videoProvider: null, videoTimer: null, videoPollStarted: null};
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

const lipsyncForm = document.querySelector('#lipsync-form');
const lipsyncMode = document.querySelector('#lipsync-mode');
const lipsyncSource = document.querySelector('#lipsync-source');
const lipsyncAudio = document.querySelector('#lipsync-audio');
const lipsyncProvider = document.querySelector('#lipsync-provider');
const lipsyncProviderNote = document.querySelector('#lipsync-provider-note');
let sourceObjectUrl = null;
let audioObjectUrl = null;

function showLipsyncState(stage, text, kind = '') {
  const root = document.querySelector('#lipsync-state');
  root.className = `render-state ${kind || stage.toLowerCase()}`;
  root.innerHTML = `<strong>${escapeHtml(stage)}</strong><span>${escapeHtml(text)}</span>`;
}

function clearObjectUrl(value) {
  if (value) URL.revokeObjectURL(value);
  return null;
}

function previewSource(file, url = null) {
  sourceObjectUrl = clearObjectUrl(sourceObjectUrl);
  const image = document.querySelector('#lipsync-image-preview');
  const video = document.querySelector('#lipsync-video-preview');
  const placeholder = document.querySelector('#lipsync-source-placeholder');
  image.classList.add('hidden'); video.classList.add('hidden'); placeholder.classList.add('hidden');
  const src = url || (file ? URL.createObjectURL(file) : '');
  if (!src) { placeholder.classList.remove('hidden'); return; }
  if (!url) sourceObjectUrl = src;
  if (lipsyncMode.value === 'portrait') { image.src = src; image.classList.remove('hidden'); }
  else { video.src = src; video.classList.remove('hidden'); }
}

function previewAudio(file, url = null) {
  audioObjectUrl = clearObjectUrl(audioObjectUrl);
  const audio = document.querySelector('#lipsync-audio-preview');
  const placeholder = document.querySelector('#lipsync-audio-placeholder');
  const src = url || (file ? URL.createObjectURL(file) : '');
  if (!src) { audio.classList.add('hidden'); placeholder.classList.remove('hidden'); return; }
  if (!url) audioObjectUrl = src;
  audio.src = src; audio.classList.remove('hidden'); placeholder.classList.add('hidden');
}

function lipsyncFormData() {
  const form = new FormData(lipsyncForm);
  form.set('mode', lipsyncMode.value);
  form.set('language', 'ml');
  return form;
}

function selectedLipsyncProvider() {
  return state.lipsyncProviders.find(provider => provider.provider_id === lipsyncProvider.value);
}

function refreshLipsyncProvider() {
  const provider = selectedLipsyncProvider();
  if (!provider) return;
  const requirements = provider.requirements?.length ? ` Requirements: ${provider.requirements.join('; ')}.` : '';
  lipsyncProviderNote.textContent = `${provider.note}${requirements} Animal support: ${provider.animal_support}.`;
  const available = provider.configured && provider.performs_real_lipsync && provider.availability === 'available';
  const generate = document.querySelector('#lipsync-generate');
  generate.disabled = !available || !state.lipsyncUploadId;
  generate.textContent = available ? 'Generate real lip-sync' : 'Generation unavailable';
  if (!available) showLipsyncState('UNAVAILABLE', provider.note, 'unavailable');
}

async function loadLipsyncCapabilities() {
  try {
    const data = await jsonOrError(await fetch('/api/lipsync/capabilities'));
    state.lipsyncProviders = data.providers;
    lipsyncProvider.replaceChildren(...data.providers.map(provider => {
      const option = document.createElement('option');
      option.value = provider.provider_id;
      option.textContent = `${provider.name} — ${provider.availability.replaceAll('_', ' ')}`;
      return option;
    }));
    const available = data.providers.filter(provider => provider.configured && provider.availability === 'available');
    document.querySelector('#lipsync-availability').textContent = available.length ? `${available.length} provider(s) ready` : 'No inference provider';
    refreshLipsyncProvider();
  } catch (error) { showLipsyncState('FAILED', error.message, 'failed'); }
}

lipsyncMode.addEventListener('change', () => {
  lipsyncSource.value = '';
  state.lipsyncUploadId = null;
  previewSource(null);
  if (lipsyncMode.value === 'portrait') {
    lipsyncSource.accept = '.png,.jpg,.jpeg,image/png,image/jpeg';
    document.querySelector('#lipsync-source-limit').textContent = 'PNG/JPG · 10 MB';
  } else {
    lipsyncSource.accept = '.mp4,video/mp4';
    document.querySelector('#lipsync-source-limit').textContent = 'MP4 · 100 MB';
  }
  refreshLipsyncProvider();
});

lipsyncSource.addEventListener('change', () => {
  state.lipsyncUploadId = null;
  previewSource(lipsyncSource.files[0]);
  refreshLipsyncProvider();
});
lipsyncAudio.addEventListener('change', () => {
  state.lipsyncUploadId = null;
  previewAudio(lipsyncAudio.files[0]);
  refreshLipsyncProvider();
});
lipsyncProvider.addEventListener('change', refreshLipsyncProvider);

document.querySelector('#lipsync-validate').addEventListener('click', async event => {
  event.target.disabled = true;
  showLipsyncState('VALIDATING', 'Checking filenames, file sizes, Malayalam language metadata, and media signatures.');
  try {
    const result = await jsonOrError(await fetch('/api/lipsync/validate', {method: 'POST', body: lipsyncFormData()}));
    showLipsyncState('VALIDATED', `${result.source.filename} and ${result.audio.filename} passed preliminary validation. No model was run.`, 'completed');
  } catch (error) { showLipsyncState('FAILED', error.message, 'failed'); }
  finally { event.target.disabled = false; }
});

document.querySelector('#lipsync-prepare').addEventListener('click', async event => {
  event.target.disabled = true;
  showLipsyncState('PREPARING', 'Validating and storing media in an isolated local UUID directory.');
  try {
    const upload = await jsonOrError(await fetch('/api/lipsync/uploads', {method: 'POST', body: lipsyncFormData()}));
    state.lipsyncUploadId = upload.upload_id;
    previewSource(null, upload.source_preview_url);
    previewAudio(null, upload.audio_preview_url);
    showLipsyncState('VALIDATED', `Prepared ${upload.request.character_id} locally. Malayalam audio was preserved byte-for-byte; inference has not run.`, 'completed');
    refreshLipsyncProvider();
  } catch (error) { showLipsyncState('FAILED', error.message, 'failed'); }
  finally { event.target.disabled = false; }
});

async function pollLipsyncJob(jobId) {
  clearTimeout(state.lipsyncTimer);
  try {
    const job = await jsonOrError(await fetch(`/api/lipsync/jobs/${jobId}`));
    showLipsyncState(job.state, job.error || job.message, job.state === 'COMPLETED' ? 'completed' : job.state === 'FAILED' ? 'failed' : '');
    if (job.state === 'COMPLETED') {
      const url = `/api/lipsync/jobs/${jobId}/output`;
      document.querySelector('#lipsync-result-video').src = url;
      document.querySelector('#lipsync-download').href = url;
      document.querySelector('#lipsync-result').classList.remove('hidden');
    } else if (job.state !== 'FAILED') state.lipsyncTimer = setTimeout(() => pollLipsyncJob(jobId), 1500);
  } catch (error) { showLipsyncState('FAILED', error.message, 'failed'); }
}

document.querySelector('#lipsync-generate').addEventListener('click', async () => {
  const form = new FormData();
  form.set('upload_id', state.lipsyncUploadId);
  form.set('provider_id', lipsyncProvider.value);
  try {
    const job = await jsonOrError(await fetch('/api/lipsync/jobs', {method: 'POST', body: form}));
    showLipsyncState(job.state, job.message); pollLipsyncJob(job.job_id);
  } catch (error) { showLipsyncState('UNAVAILABLE', error.message, 'unavailable'); }
});

loadLipsyncCapabilities();

const videoImageInput = document.querySelector('#video-image-input');
const videoDropZone = document.querySelector('#video-drop-zone');
const videoGenerateButton = document.querySelector('#video-generate-button');
let videoImageObjectUrl = null;

function showVideoState(stage, text, kind = '') {
  const root = document.querySelector('#video-generation-state');
  root.className = `render-state ${kind || stage.toLowerCase()}`;
  root.innerHTML = `<strong>${escapeHtml(stage.replaceAll('_', ' '))}</strong><span>${escapeHtml(text)}</span>`;
}

function videoCanGenerate() {
  const provider = state.videoProvider;
  const prompt = document.querySelector('#video-prompt').value.trim();
  const consent = document.querySelector('#video-remote-consent').checked;
  return Boolean(provider?.configured && state.videoUploadId && prompt.length >= 10 && consent);
}

function refreshVideoGenerateButton() {
  videoGenerateButton.disabled = !videoCanGenerate();
}

function populateVideoSettings(provider) {
  const resolution = document.querySelector('#video-resolution');
  resolution.replaceChildren(...Object.entries(provider.resolution_presets).map(([name, dimensions]) => {
    const option = document.createElement('option');
    option.value = dimensions.join('x');
    option.textContent = `${name} · ${dimensions[0]}×${dimensions[1]}`;
    return option;
  }));
  const duration = document.querySelector('#video-duration');
  duration.replaceChildren(...provider.supported_durations.map(value => {
    const option = document.createElement('option'); option.value = value; option.textContent = `${value} second${value === 1 ? '' : 's'}`; return option;
  }));
  duration.value = provider.supported_durations.includes(3) ? '3' : String(provider.supported_durations[0]);
  const decoder = document.querySelector('#video-decoder');
  decoder.replaceChildren(...provider.supported_decoders.map(value => {
    const option = document.createElement('option'); option.value = value; option.textContent = value; return option;
  }));
  document.querySelector('#video-enhance-prompt').closest('label').classList.toggle('hidden', !provider.supports_prompt_enhancement);
  document.querySelector('#video-seed').closest('div').classList.toggle('hidden', !provider.supports_seed);
}

async function loadVideoCapabilities() {
  try {
    const data = await jsonOrError(await fetch('/api/video/capabilities'));
    state.videoProvider = data.provider;
    populateVideoSettings(data.provider);
    const status = document.querySelector('#video-provider-status');
    status.textContent = data.provider.configured ? 'Provider ready' : data.provider.state.replaceAll('_', ' ');
    document.querySelector('#video-provider-note').textContent = `${data.provider.note} ${data.remote_disclosure}`;
    const guidance = document.querySelector('#video-prompt-guidance');
    guidance.replaceChildren(...data.character_consistency_guidance.map(text => {
      const item = document.createElement('li'); item.textContent = text; return item;
    }));
    if (!data.provider.configured) showVideoState('NOT_CONFIGURED', data.provider.note, 'unavailable');
    refreshVideoGenerateButton();
  } catch (error) { showVideoState('FAILED', error.message, 'failed'); }
}

function previewVideoImage(file) {
  if (videoImageObjectUrl) URL.revokeObjectURL(videoImageObjectUrl);
  videoImageObjectUrl = file ? URL.createObjectURL(file) : null;
  const preview = document.querySelector('#video-image-preview');
  const placeholder = document.querySelector('#video-image-placeholder');
  if (!videoImageObjectUrl) { preview.classList.add('hidden'); placeholder.classList.remove('hidden'); return; }
  preview.src = videoImageObjectUrl;
  preview.classList.remove('hidden'); placeholder.classList.add('hidden');
}

async function prepareVideoImage(file) {
  state.videoUploadId = null;
  refreshVideoGenerateButton();
  previewVideoImage(file);
  if (!file) return;
  say('Validating and saving the reference image locally…', 'notice', document.querySelector('#video-upload-message'));
  const form = new FormData(); form.set('image', file);
  try {
    const upload = await jsonOrError(await fetch('/api/video/uploads', {method: 'POST', body: form}));
    state.videoUploadId = upload.upload_id;
    document.querySelector('#video-image-preview').src = upload.preview_url;
    say(`Prepared ${upload.original_filename} locally (${Math.round(upload.bytes / 1024)} KB).`, 'success', document.querySelector('#video-upload-message'));
  } catch (error) {
    previewVideoImage(null);
    say(error.message, 'error', document.querySelector('#video-upload-message'));
  }
  refreshVideoGenerateButton();
}

videoImageInput.addEventListener('change', () => prepareVideoImage(videoImageInput.files[0]));
['dragenter', 'dragover'].forEach(type => videoDropZone.addEventListener(type, event => {
  event.preventDefault(); videoDropZone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach(type => videoDropZone.addEventListener(type, event => {
  event.preventDefault(); videoDropZone.classList.remove('dragging');
}));
videoDropZone.addEventListener('drop', event => {
  const file = event.dataTransfer.files[0];
  if (file) prepareVideoImage(file);
});
document.querySelector('#video-prompt').addEventListener('input', refreshVideoGenerateButton);
document.querySelector('#video-remote-consent').addEventListener('change', refreshVideoGenerateButton);
document.querySelector('#video-random-seed').addEventListener('change', event => {
  document.querySelector('#video-seed').disabled = event.target.checked;
});
document.querySelector('#video-seed').disabled = true;

function videoJobPayload() {
  const [width, height] = document.querySelector('#video-resolution').value.split('x').map(Number);
  return {
    upload_id: state.videoUploadId,
    provider_id: document.querySelector('#video-provider').value,
    prompt: document.querySelector('#video-prompt').value,
    remote_processing_consent: true,
    settings: {
      duration_seconds: Number(document.querySelector('#video-duration').value),
      width, height,
      seed: Number(document.querySelector('#video-seed').value),
      decoder: document.querySelector('#video-decoder').value,
      auto_length: document.querySelector('#video-auto-length').checked,
      randomize_seed: document.querySelector('#video-random-seed').checked,
      enhance_prompt: document.querySelector('#video-enhance-prompt').checked,
    },
  };
}

function showVideoMetadata(job) {
  const root = document.querySelector('#video-result-metadata');
  const values = {
    Provider: job.provider_name,
    Model: job.model_id,
    Resolution: `${job.metadata.width}×${job.metadata.height}`,
    Duration: `${job.metadata.duration_seconds.toFixed(2)} s`,
    'Frame rate': `${job.metadata.frame_rate.toFixed(2)} fps`,
    Codec: job.metadata.codec,
    'Provider job': job.provider_job_id,
    Seed: job.effective_seed,
    Prompt: job.prompt,
  };
  root.replaceChildren(...Object.entries(values).flatMap(([label, value]) => {
    const term = document.createElement('dt'); term.textContent = label;
    const description = document.createElement('dd'); description.textContent = value ?? 'Not reported';
    return [term, description];
  }));
  root.classList.remove('hidden');
}

async function pollVideoJob(jobId) {
  clearTimeout(state.videoTimer);
  if (Date.now() - state.videoPollStarted > 20 * 60 * 1000) {
    showVideoState('FAILED', 'Browser polling stopped after 20 minutes. Reopen the job status endpoint to inspect the server state.', 'failed');
    videoGenerateButton.disabled = false;
    return;
  }
  try {
    const job = await jsonOrError(await fetch(`/api/video/jobs/${jobId}`));
    showVideoState(job.state, job.error || job.message, job.state === 'COMPLETED' ? 'completed' : job.state === 'FAILED' ? 'failed' : '');
    if (job.state === 'COMPLETED') {
      const url = `/api/video/jobs/${jobId}/output`;
      document.querySelector('#ai-video-player').src = url;
      document.querySelector('#ai-video-download').href = url;
      document.querySelector('#ai-video-result').classList.remove('hidden');
      showVideoMetadata(job);
      videoGenerateButton.disabled = false;
    } else if (['FAILED', 'CANCELLED'].includes(job.state)) videoGenerateButton.disabled = false;
    else state.videoTimer = setTimeout(() => pollVideoJob(jobId), 1500);
  } catch (error) { showVideoState('FAILED', error.message, 'failed'); videoGenerateButton.disabled = false; }
}

videoGenerateButton.addEventListener('click', async () => {
  if (!videoCanGenerate()) return;
  videoGenerateButton.disabled = true;
  document.querySelector('#ai-video-result').classList.add('hidden');
  document.querySelector('#video-result-metadata').classList.add('hidden');
  showVideoState('SUBMITTING', 'Submitting the approved reference image and prompt to Hugging Face.');
  try {
    const job = await jsonOrError(await fetch('/api/video/jobs', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(videoJobPayload()),
    }));
    state.videoPollStarted = Date.now();
    showVideoState(job.state, job.message); pollVideoJob(job.job_id);
  } catch (error) { showVideoState('FAILED', error.message, 'failed'); refreshVideoGenerateButton(); }
});

loadVideoCapabilities();
