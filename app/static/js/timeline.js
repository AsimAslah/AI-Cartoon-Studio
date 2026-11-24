(() => {
  const state = {
    clips: [], projectId: null, projectKind: 'timeline', templateId: null,
    voice: null, music: null, logos: [], capabilities: null,
    selectedCharacters: new Set(), characterTemplates: [], exportTimer: null, previewTimer: null,
  };
  const q = selector => document.querySelector(selector);
  const clipRoot = q('#timeline-clips');
  const videoPreview = q('#timeline-preview');
  const imagePreview = q('#timeline-image-preview');
  const cardPreview = q('#timeline-card-preview');
  const exportButton = q('#timeline-export');

  async function json(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map(item => item.msg).join(' ') : data.detail?.message || 'Timeline request failed.';
      throw new Error(detail);
    }
    return data;
  }

  function message(text, kind = 'notice') { q('#timeline-message').textContent = text; q('#timeline-message').className = kind; }
  function exportState(stage, text, kind = '') {
    const root = q('#timeline-export-state'); root.className = `render-state ${kind || stage.toLowerCase()}`; root.replaceChildren();
    const strong = document.createElement('strong'); strong.textContent = stage.replaceAll('_', ' ');
    const span = document.createElement('span'); span.textContent = text; root.append(strong, span);
  }
  function button(text, className = '') { const el = document.createElement('button'); el.type = 'button'; el.textContent = text; el.className = className; return el; }
  function field(labelText, type, value, onChange, options = {}) {
    const wrap = document.createElement('div'); if (options.wide) wrap.className = 'wide';
    const label = document.createElement('label'); label.textContent = labelText;
    const input = document.createElement(type === 'textarea' ? 'textarea' : 'input');
    if (type !== 'textarea') input.type = type;
    Object.entries(options).forEach(([key, option]) => { if (key !== 'wide') input[key] = option; });
    input.value = value ?? ''; input.addEventListener(type === 'range' ? 'input' : 'change', () => onChange(input));
    wrap.append(label, input); return wrap;
  }
  function selectField(labelText, value, entries, onChange) {
    const wrap = document.createElement('div'); const label = document.createElement('label'); label.textContent = labelText;
    const select = document.createElement('select');
    entries.forEach(([entryValue, text]) => { const option = document.createElement('option'); option.value = entryValue; option.textContent = text; select.append(option); });
    select.value = value; select.addEventListener('change', () => onChange(select.value)); wrap.append(label, select); return wrap;
  }

  function defaults(clip) {
    return Object.assign({
      clip_id: crypto.randomUUID(), media_id: null, order: 0, trim_start_seconds: 0, trim_end_seconds: null, volume: 1,
      scene_type: 'video', slot_key: null, slot_title: null, slot_description: null, duration_seconds: 3,
      fade_in_seconds: 0, fade_out_seconds: 0, transition_to_next: 'cut', transition_duration_seconds: .5,
      title_text: null, overlay_text: null, text_position: 'lower_third', font_size: 48, brightness: 0, contrast: 1,
      logo_media_id: null, requires_verified_lipsync: false, lipsync_verified: false, media: null,
    }, clip);
  }
  function newMediaScene(media, sceneType) {
    return defaults({
      media_id: media.media_id, order: state.clips.length, scene_type: sceneType, media,
      trim_end_seconds: sceneType === 'video' ? media.duration_seconds : null,
      duration_seconds: sceneType === 'still' ? 3 : media.duration_seconds,
    });
  }
  function normalizeOrders() { state.clips.forEach((clip, index) => { clip.order = index; }); }
  function clipDuration(clip) {
    if (clip.scene_type === 'video') return clip.media ? Math.max(0, Number(clip.trim_end_seconds ?? clip.media.duration_seconds) - Number(clip.trim_start_seconds)) : 0;
    return Number(clip.duration_seconds || 0);
  }
  function totalDuration() {
    return state.clips.reduce((total, clip, index) => {
      let next = total + clipDuration(clip);
      if (index < state.clips.length - 1 && clip.transition_to_next === 'crossfade') next -= Math.min(clip.transition_duration_seconds, clipDuration(clip));
      return next;
    }, 0);
  }
  function refreshExportButton() {
    const available = state.capabilities?.ffmpeg_available && state.capabilities?.ffprobe_available;
    exportButton.disabled = !(available && state.clips.length);
  }
  function markDirty() { refreshExportButton(); }

  function renderAssignmentTargets() {
    const select = q('#timeline-assignment-target'); const selected = select.value; select.replaceChildren();
    const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'Append as new scene'; select.append(blank);
    state.clips.filter(clip => !clip.media_id && ['video', 'still'].includes(clip.scene_type)).forEach((clip, index) => {
      const option = document.createElement('option'); option.value = clip.clip_id; option.textContent = `${index + 1}. ${clip.slot_title || 'Planned scene'}`; select.append(option);
    });
    select.value = [...select.options].some(option => option.value === selected) ? selected : '';
  }

  function updateClipType(clip, type) {
    const expected = type === 'video' ? 'clip' : type === 'still' ? 'image' : null;
    if (!expected || (clip.media && clip.media.kind !== expected)) { clip.media = null; clip.media_id = null; }
    clip.scene_type = type;
    if (['title_card', 'branding_card'].includes(type) && !clip.title_text) clip.title_text = type === 'branding_card' ? 'BRAND' : 'Title';
    markDirty(); renderTimeline();
  }

  function renderTimeline() {
    normalizeOrders(); clipRoot.replaceChildren();
    if (!state.clips.length) { const empty = document.createElement('p'); empty.className = 'muted'; empty.textContent = 'No scenes yet.'; clipRoot.append(empty); }
    state.clips.forEach((item, index) => {
      const clip = state.clips[index] = defaults(item);
      const card = document.createElement('article'); card.className = 'timeline-clip';
      if (clip.media) { const image = document.createElement('img'); image.src = clip.media.thumbnail_url || clip.media.preview_url; image.alt = `Preview for ${clip.media.original_filename}`; card.append(image); }
      else { const plan = document.createElement('div'); plan.className = 'timeline-scene-plan'; plan.textContent = ['title_card', 'branding_card'].includes(clip.scene_type) ? 'Configured local card' : 'PLANNED — media not assigned'; card.append(plan); }

      const body = document.createElement('div');
      const title = document.createElement('h4'); title.textContent = `${index + 1}. ${clip.slot_title || clip.media?.original_filename || 'Untitled scene'}`; body.append(title);
      if (clip.slot_description) { const description = document.createElement('p'); description.className = 'muted'; description.textContent = clip.slot_description; body.append(description); }
      const details = document.createElement('small');
      details.textContent = clip.media ? `${clip.media.width}×${clip.media.height} · ${Number(clip.media.duration_seconds).toFixed(2)}s · ${clip.media.codec}` : `${clip.scene_type.replaceAll('_', ' ')} · ${clipDuration(clip).toFixed(2)}s`;
      body.append(details);

      const basics = document.createElement('div'); basics.className = 'timeline-clip-fields';
      if (clip.scene_type === 'video' && clip.media) {
        basics.append(
          field('Trim start (s)', 'number', clip.trim_start_seconds, input => { clip.trim_start_seconds = Math.max(0, Number(input.value)); renderDuration(); }, {min: 0, max: clip.media.duration_seconds, step: .01}),
          field('Trim end (s)', 'number', clip.trim_end_seconds ?? clip.media.duration_seconds, input => { clip.trim_end_seconds = Number(input.value); renderDuration(); }, {min: .01, max: clip.media.duration_seconds, step: .01}),
          field('Scene audio volume', 'range', clip.volume, input => { clip.volume = Number(input.value); }, {min: 0, max: 2, step: .05}),
        );
      } else {
        basics.append(field('Scene duration (s)', 'number', clip.duration_seconds, input => { clip.duration_seconds = Number(input.value); renderDuration(); }, {min: .1, max: 60, step: .1}));
      }
      body.append(basics);

      const cinema = document.createElement('div'); cinema.className = 'timeline-cinematic-fields';
      cinema.append(
        selectField('Scene type', clip.scene_type, [['video', 'Video'], ['still', 'Still image'], ['title_card', 'Title card'], ['branding_card', 'Branding card']], value => updateClipType(clip, value)),
        field('Fade in (s)', 'number', clip.fade_in_seconds, input => { clip.fade_in_seconds = Number(input.value); }, {min: 0, max: 5, step: .1}),
        field('Fade out (s)', 'number', clip.fade_out_seconds, input => { clip.fade_out_seconds = Number(input.value); }, {min: 0, max: 5, step: .1}),
        selectField('Transition to next', index === state.clips.length - 1 ? 'cut' : clip.transition_to_next, [['cut', 'Cut'], ['crossfade', 'Crossfade']], value => { clip.transition_to_next = value; renderDuration(); }),
        field('Transition duration', 'number', clip.transition_duration_seconds, input => { clip.transition_duration_seconds = Number(input.value); renderDuration(); }, {min: .1, max: 3, step: .1, disabled: index === state.clips.length - 1}),
        field('Brightness', 'number', clip.brightness, input => { clip.brightness = Number(input.value); }, {min: -1, max: 1, step: .05}),
        field('Contrast', 'number', clip.contrast, input => { clip.contrast = Number(input.value); }, {min: .5, max: 2, step: .05}),
        selectField('Text position', clip.text_position, [['top', 'Top'], ['center', 'Center'], ['lower_third', 'Lower third']], value => { clip.text_position = value; }),
        field('Font size', 'number', clip.font_size, input => { clip.font_size = Number(input.value); }, {min: 12, max: 96, step: 1}),
        field('Title/card text', 'textarea', clip.title_text || '', input => { clip.title_text = input.value || null; }, {wide: true, maxLength: 200}),
        field('Overlay text', 'textarea', clip.overlay_text || '', input => { clip.overlay_text = input.value || null; }, {wide: true, maxLength: 300}),
      );
      const logoEntries = [['', 'No logo'], ...state.logos.map(logo => [logo.media_id, logo.original_filename])];
      cinema.append(selectField('Logo overlay', clip.logo_media_id || '', logoEntries, value => { clip.logo_media_id = value || null; }));
      if (clip.requires_verified_lipsync) {
        const verify = field('Verified visible lip-sync', 'checkbox', '', input => { clip.lipsync_verified = input.checked; }, {});
        verify.querySelector('input').checked = clip.lipsync_verified; cinema.append(verify);
      }
      body.append(cinema);

      const actions = document.createElement('div'); actions.className = 'timeline-clip-actions';
      const play = button('Preview', 'secondary'); play.addEventListener('click', () => previewScene(index, false));
      const up = button('↑', 'secondary'); up.disabled = index === 0; up.addEventListener('click', () => moveClip(index, -1));
      const down = button('↓', 'secondary'); down.disabled = index === state.clips.length - 1; down.addEventListener('click', () => moveClip(index, 1));
      const remove = button('Remove', 'secondary'); remove.addEventListener('click', () => { state.clips.splice(index, 1); renderTimeline(); });
      actions.append(play, up, down, remove); card.append(body, actions); clipRoot.append(card);
    });
    if (state.clips.length) state.clips[state.clips.length - 1].transition_to_next = 'cut';
    renderDuration(); renderAssignmentTargets(); refreshExportButton();
  }

  function renderDuration() { q('#timeline-duration').textContent = `${Math.max(0, totalDuration()).toFixed(2)} seconds`; }
  function moveClip(index, direction) { const target = index + direction; if (target < 0 || target >= state.clips.length) return; [state.clips[index], state.clips[target]] = [state.clips[target], state.clips[index]]; renderTimeline(); }
  function hidePreviews() { clearTimeout(state.previewTimer); videoPreview.pause(); videoPreview.classList.add('hidden'); imagePreview.classList.add('hidden'); cardPreview.classList.add('hidden'); }
  function previewScene(index, sequence) {
    const clip = state.clips[index]; hidePreviews();
    if (!clip) { message('Available-scene sequence preview completed.', 'success'); return; }
    const next = () => { if (sequence) previewScene(index + 1, true); };
    if (clip.scene_type === 'video' && clip.media) {
      videoPreview.classList.remove('hidden'); videoPreview.src = clip.media.preview_url; videoPreview.load();
      videoPreview.onloadedmetadata = () => { videoPreview.currentTime = Number(clip.trim_start_seconds); videoPreview.play().catch(() => message('Select play to continue the preview.', 'warning')); };
      videoPreview.ontimeupdate = () => { if (videoPreview.currentTime >= Number(clip.trim_end_seconds ?? clip.media.duration_seconds) - .03) { videoPreview.pause(); next(); } };
    } else if (clip.scene_type === 'still' && clip.media) {
      imagePreview.src = clip.media.preview_url; imagePreview.classList.remove('hidden'); if (sequence) state.previewTimer = setTimeout(next, clip.duration_seconds * 1000);
    } else if (['title_card', 'branding_card'].includes(clip.scene_type)) {
      cardPreview.textContent = clip.title_text || ''; cardPreview.classList.remove('hidden'); if (sequence) state.previewTimer = setTimeout(next, clip.duration_seconds * 1000);
    } else { message(`Scene ${index + 1} remains planned and was skipped.`, 'warning'); if (sequence) state.previewTimer = setTimeout(next, 250); }
  }

  async function uploadMedia(file, kind) { const form = new FormData(); form.set('kind', kind); form.set('media', file); return json(await fetch('/api/timeline/media', {method: 'POST', body: form})); }
  function assignMedia(media, sceneType) {
    const targetId = q('#timeline-assignment-target').value;
    const target = state.clips.find(clip => clip.clip_id === targetId);
    if (target) {
      target.media = media; target.media_id = media.media_id; target.scene_type = sceneType; target.trim_start_seconds = 0;
      target.trim_end_seconds = sceneType === 'video' ? media.duration_seconds : null; target.duration_seconds = sceneType === 'still' ? 3 : media.duration_seconds;
      q('#timeline-assignment-target').value = '';
    } else state.clips.push(newMediaScene(media, sceneType));
    renderTimeline();
  }
  async function addFiles(inputSelector, kind, sceneType) {
    const input = q(inputSelector); const files = [...input.files]; if (!files.length) { message('Choose media files first.', 'warning'); return; }
    try { for (const file of files) { message(`Validating and preserving ${file.name}.`); assignMedia(await uploadMedia(file, kind), sceneType); } input.value = ''; message(`${files.length} media file(s) preserved locally.`, 'success'); }
    catch (error) { message(error.message, 'error'); }
  }
  async function importGenerated() {
    const id = q('#timeline-generated-clips').value; if (!id) { message('Choose a generated clip first.', 'warning'); return; }
    try { assignMedia(await json(await fetch('/api/timeline/import-generated', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job_id: id})})), 'video'); message('Generated clip copied without changing its original.', 'success'); }
    catch (error) { message(error.message, 'error'); }
  }
  async function uploadLogo() {
    const file = q('#timeline-logo-input').files[0]; if (!file) { message('Choose a logo image first.', 'warning'); return; }
    try { const logo = await uploadMedia(file, 'logo'); state.logos.push(logo); q('#timeline-logo-name').textContent = logo.original_filename; q('#timeline-logo-input').value = ''; renderTimeline(); message('Logo preserved for explicit scene overlays.', 'success'); }
    catch (error) { message(error.message, 'error'); }
  }

  function projectDraft() {
    normalizeOrders();
    return {
      schema_version: '1.1', name: q('#timeline-project-name').value.trim() || 'Untitled advertisement', project_kind: state.projectKind,
      template_id: state.templateId, clips: state.clips.map(({media, ...clip}) => clip),
      voice_track: state.voice ? {media_id: state.voice.media_id, volume: Number(q('#timeline-voice-volume').value), start_seconds: Number(q('#timeline-voice-offset').value)} : null,
      music_track: state.music ? {media_id: state.music.media_id, volume: Number(q('#timeline-music-volume').value), start_seconds: Number(q('#timeline-music-offset').value)} : null,
      character_reference_ids: [...state.selectedCharacters], export_profile: q('#timeline-profile').value,
    };
  }
  async function saveProject() {
    const url = state.projectId ? `/api/timeline/projects/${state.projectId}` : '/api/timeline/projects';
    const project = await json(await fetch(url, {method: state.projectId ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(projectDraft())}));
    state.projectId = project.project_id; await loadProjectList(project.project_id); message(`Saved ${project.name}. Planned scenes remain explicitly unassigned.`, 'success'); return project;
  }
  async function loadProjectList(selected = state.projectId) {
    const data = await json(await fetch('/api/timeline/projects')); const select = q('#timeline-projects'); select.replaceChildren();
    const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'New unsaved project'; select.append(blank);
    data.projects.forEach(project => { const option = document.createElement('option'); option.value = project.project_id; option.textContent = `${project.name} · ${project.clip_count} scenes`; select.append(option); }); select.value = selected || '';
  }
  async function loadProject() {
    const id = q('#timeline-projects').value; if (!id) { newProject(); return; }
    try {
      const project = await json(await fetch(`/api/timeline/projects/${id}`));
      state.clips = await Promise.all(project.clips.map(async clip => defaults({...clip, media: clip.media_id ? await json(await fetch(`/api/timeline/media/${clip.media_id}`)) : null})));
      state.projectId = project.project_id; state.projectKind = project.project_kind; state.templateId = project.template_id;
      state.voice = project.voice_track ? await json(await fetch(`/api/timeline/media/${project.voice_track.media_id}`)) : null;
      state.music = project.music_track ? await json(await fetch(`/api/timeline/media/${project.music_track.media_id}`)) : null;
      const logoIds = [...new Set(project.clips.map(clip => clip.logo_media_id).filter(Boolean))]; state.logos = await Promise.all(logoIds.map(async idValue => json(await fetch(`/api/timeline/media/${idValue}`))));
      state.selectedCharacters = new Set(project.character_reference_ids || []); q('#timeline-project-name').value = project.name; q('#timeline-profile').value = project.export_profile;
      q('#timeline-voice-volume').value = project.voice_track?.volume ?? 1; q('#timeline-voice-offset').value = project.voice_track?.start_seconds ?? 0;
      q('#timeline-music-volume').value = project.music_track?.volume ?? .35; q('#timeline-music-offset').value = project.music_track?.start_seconds ?? 0;
      renderAudio(); await loadCharacters(); renderTimeline(); message(`Opened ${project.name}.`, 'success');
    } catch (error) { message(error.message, 'error'); }
  }
  function newProject() {
    hidePreviews(); state.clips = []; state.projectId = null; state.projectKind = 'timeline'; state.templateId = null; state.voice = null; state.music = null; state.logos = []; state.selectedCharacters = new Set();
    q('#timeline-project-name').value = 'Untitled advertisement'; q('#timeline-profile').value = '720p'; q('#timeline-projects').value = ''; renderAudio(); renderTimeline(); loadCharacters().catch(error => message(error.message, 'error')); message('Started a new local project.');
  }
  async function loadWoodoraTemplate() {
    try { const data = await json(await fetch('/api/timeline/templates/woodora-grand-arrival')); const project = data.project; state.clips = project.clips.map(defaults); state.projectId = null; state.projectKind = project.project_kind; state.templateId = project.template_id; state.voice = null; state.music = null; state.logos = []; state.selectedCharacters = new Set(); state.characterTemplates = data.character_templates; q('#timeline-project-name').value = project.name; fillCharacterTemplates(); renderAudio(); await loadCharacters(); renderTimeline(); message(data.warning, 'warning'); }
    catch (error) { message(error.message, 'error'); }
  }
  function addCard(type) { state.clips.push(defaults({order: state.clips.length, scene_type: type, duration_seconds: 3, title_text: type === 'branding_card' ? 'BRAND' : 'Opening title'})); state.projectKind = 'advertisement'; renderTimeline(); }

  function renderAudio() { q('#timeline-voice-name').textContent = state.voice?.original_filename || 'No voice track.'; q('#timeline-music-name').textContent = state.music?.original_filename || 'No music track.'; q('#timeline-voice-volume-label').textContent = `${Math.round(Number(q('#timeline-voice-volume').value) * 100)}%`; q('#timeline-music-volume-label').textContent = `${Math.round(Number(q('#timeline-music-volume').value) * 100)}%`; }
  async function selectAudio(event, kind) { const file = event.target.files[0]; if (!file) return; try { state[kind] = await uploadMedia(file, kind); renderAudio(); message(`${kind === 'voice' ? 'Malayalam voice' : 'Background music'} preserved locally.`, 'success'); } catch (error) { message(error.message, 'error'); event.target.value = ''; } }

  function fillCharacterTemplates() { const select = q('#timeline-character-template'); select.replaceChildren(); const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'Blank character'; select.append(blank); state.characterTemplates.forEach(template => { const option = document.createElement('option'); option.value = template.template_id; option.textContent = template.name; select.append(option); }); }
  function applyCharacterTemplate() { const template = state.characterTemplates.find(item => item.template_id === q('#timeline-character-template').value); if (!template) return; q('#timeline-character-name').value = template.name; q('#timeline-character-description').value = template.visual_description; q('#timeline-character-clothing').value = template.clothing_accessories; q('#timeline-character-notes').value = template.notes; }
  function renderCharacters(references) { const root = q('#timeline-character-list'); root.replaceChildren(); if (!references.length) { const empty = document.createElement('p'); empty.className = 'muted'; empty.textContent = 'No saved character references.'; root.append(empty); return; } references.forEach(reference => { const item = document.createElement('label'); item.className = 'timeline-character-item'; const check = document.createElement('input'); check.type = 'checkbox'; check.checked = state.selectedCharacters.has(reference.reference_id); check.addEventListener('change', () => check.checked ? state.selectedCharacters.add(reference.reference_id) : state.selectedCharacters.delete(reference.reference_id)); const text = document.createTextNode(` ${reference.name} · ${reference.image_count} image(s)`); item.append(check, text); root.append(item); }); }
  async function loadCharacters() { const data = await json(await fetch('/api/timeline/characters')); renderCharacters(data.references); }
  async function saveCharacter() {
    try {
      const imageIds = []; for (const file of [...q('#timeline-character-images').files]) imageIds.push((await uploadMedia(file, 'character_reference')).media_id);
      const draft = {schema_version: '1.0', name: q('#timeline-character-name').value.trim(), visual_description: q('#timeline-character-description').value.trim(), clothing_accessories: q('#timeline-character-clothing').value, notes: q('#timeline-character-notes').value, image_media_ids: imageIds};
      const record = await json(await fetch('/api/timeline/characters', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(draft)})); state.selectedCharacters.add(record.reference_id); await loadCharacters(); message(`Saved character reference ${record.name}. Identity consistency is not guaranteed.`, 'success');
    } catch (error) { message(error.message, 'error'); }
  }

  async function pollExport(jobId) { clearTimeout(state.exportTimer); try { const job = await json(await fetch(`/api/timeline/exports/${jobId}`)); exportState(job.state, job.error || job.message, job.state === 'COMPLETED' ? 'completed' : job.state === 'FAILED' ? 'failed' : ''); if (job.state === 'COMPLETED') { const url = `/api/timeline/exports/${jobId}/output`; q('#timeline-export-player').src = url; q('#timeline-export-download').href = url; q('#timeline-export-result').classList.remove('hidden'); refreshExportButton(); } else if (job.state === 'FAILED') refreshExportButton(); else state.exportTimer = setTimeout(() => pollExport(jobId), 1000); } catch (error) { exportState('FAILED', error.message, 'failed'); refreshExportButton(); } }
  async function startExport() { exportButton.disabled = true; q('#timeline-export-result').classList.add('hidden'); try { const project = await saveProject(); exportState('QUEUED', 'Submitting only assigned media and configured cards to local FFmpeg.'); const job = await json(await fetch('/api/timeline/exports', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project_id: project.project_id})})); pollExport(job.job_id); } catch (error) { exportState('FAILED', error.message, 'failed'); refreshExportButton(); } }
  async function loadCapabilities() { try { const data = await json(await fetch('/api/timeline/capabilities')); state.capabilities = data; q('#timeline-availability').textContent = data.ffmpeg_available && data.ffprobe_available && data.safe_font_available ? 'FFmpeg + safe font ready' : 'Local tools incomplete'; const generated = q('#timeline-generated-clips'); generated.replaceChildren(); const blank = document.createElement('option'); blank.value = ''; blank.textContent = data.generated_job_ids.length ? 'Choose a generated clip' : 'No generated clips detected'; generated.append(blank); data.generated_job_ids.forEach(id => { const option = document.createElement('option'); option.value = id; option.textContent = id; generated.append(option); }); const templates = await json(await fetch('/api/timeline/character-templates')); state.characterTemplates = templates.templates; fillCharacterTemplates(); await Promise.all([loadProjectList(), loadCharacters()]); refreshExportButton(); } catch (error) { message(error.message, 'error'); exportState('UNAVAILABLE', error.message, 'unavailable'); } }

  q('#timeline-upload-clips').addEventListener('click', () => addFiles('#timeline-clip-input', 'clip', 'video'));
  q('#timeline-upload-images').addEventListener('click', () => addFiles('#timeline-image-input', 'image', 'still'));
  q('#timeline-upload-logo').addEventListener('click', uploadLogo); q('#timeline-import-generated').addEventListener('click', importGenerated);
  q('#timeline-play-sequence').addEventListener('click', () => previewScene(0, true)); q('#timeline-save-project').addEventListener('click', () => saveProject().catch(error => message(error.message, 'error')));
  q('#timeline-open-project').addEventListener('click', loadProject); q('#timeline-new-project').addEventListener('click', newProject); q('#timeline-load-woodora').addEventListener('click', loadWoodoraTemplate);
  q('#timeline-add-title').addEventListener('click', () => addCard('title_card')); q('#timeline-add-brand').addEventListener('click', () => addCard('branding_card')); q('#timeline-export').addEventListener('click', startExport);
  q('#timeline-voice-input').addEventListener('change', event => selectAudio(event, 'voice')); q('#timeline-music-input').addEventListener('change', event => selectAudio(event, 'music'));
  ['voice', 'music'].forEach(kind => q(`#timeline-${kind}-volume`).addEventListener('input', renderAudio)); q('#timeline-character-template').addEventListener('change', applyCharacterTemplate); q('#timeline-save-character').addEventListener('click', saveCharacter);
  renderTimeline(); renderAudio(); loadCapabilities();
})();
