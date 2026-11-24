(() => {
  const state = {
    clips: [], projectId: null, projectKind: 'timeline', templateId: null,
    voice: null, music: null, logos: [], luts: [], capabilities: null,
    selectedCharacters: new Set(), characterTemplates: [], exportTimer: null, previewTimer: null,
    selectedClipId: null, zoom: 80, playhead: 0, restoring: false,
  };
  const model = globalThis.TimelineModel;
  const history = new model.History(50);
  const q = selector => document.querySelector(selector);
  const clipRoot = q('#timeline-clips');
  const videoPreview = q('#timeline-preview');
  const imagePreview = q('#timeline-image-preview');
  const cardPreview = q('#timeline-card-preview');
  const exportButton = q('#timeline-export');

  function audioInputs() {
    const values = {};
    ['voice', 'music'].forEach(kind => {
      ['volume', 'offset', 'sync', 'end', 'fade-in', 'fade-out'].forEach(name => {
        const input = q(`#timeline-${kind}-${name}`); if (input) values[`${kind}-${name}`] = input.value;
      });
    });
    ['voice-source-start', 'voice-source-end', 'voice-scene'].forEach(name => { values[name] = q(`#timeline-${name}`)?.value ?? ''; });
    values['ducking-enabled'] = q('#timeline-ducking-enabled')?.checked ?? true;
    values['ducking-intensity'] = q('#timeline-ducking-intensity')?.value ?? '.55';
    return values;
  }

  function snapshot() {
    return {
      clips: structuredClone(state.clips), projectKind: state.projectKind, templateId: state.templateId,
      voice: state.voice, music: state.music, logos: state.logos, luts: state.luts,
      selectedCharacters: [...state.selectedCharacters], selectedClipId: state.selectedClipId,
      zoom: state.zoom, playhead: state.playhead, audio: audioInputs(),
    };
  }

  function recordHistory() {
    if (!state.restoring) { history.record(snapshot()); updateHistoryButtons(); }
  }

  function restoreSnapshot(saved) {
    if (!saved) return;
    state.restoring = true;
    Object.assign(state, {
      clips: saved.clips, projectKind: saved.projectKind, templateId: saved.templateId,
      voice: saved.voice, music: saved.music, logos: saved.logos, luts: saved.luts,
      selectedCharacters: new Set(saved.selectedCharacters), selectedClipId: saved.selectedClipId,
      zoom: saved.zoom, playhead: saved.playhead,
    });
    Object.entries(saved.audio).forEach(([name, value]) => {
      const input = q(`#timeline-${name}`); if (!input) return;
      if (input.type === 'checkbox') input.checked = Boolean(value); else input.value = value;
    });
    q('#timeline-zoom').value = state.zoom;
    state.restoring = false; renderAudio(); renderTimeline(); updateHistoryButtons();
  }

  function undo() { const saved = history.undo(snapshot()); restoreSnapshot(saved); }
  function redo() { const saved = history.redo(snapshot()); restoreSnapshot(saved); }
  function updateHistoryButtons() { q('#timeline-undo').disabled = !history.undoStack.length; q('#timeline-redo').disabled = !history.redoStack.length; }

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
    let beforeEdit = null; input.value = value ?? ''; input.addEventListener('focus', () => { beforeEdit = snapshot(); });
    input.addEventListener(type === 'range' ? 'input' : 'change', () => { if (beforeEdit) { history.record(beforeEdit); beforeEdit = null; updateHistoryButtons(); } else recordHistory(); onChange(input); renderProfessionalTimeline(); });
    wrap.append(label, input); return wrap;
  }
  function selectField(labelText, value, entries, onChange) {
    const wrap = document.createElement('div'); const label = document.createElement('label'); label.textContent = labelText;
    const select = document.createElement('select');
    entries.forEach(([entryValue, text]) => { const option = document.createElement('option'); option.value = entryValue; option.textContent = text; select.append(option); });
    let beforeEdit = null; select.value = value; select.addEventListener('focus', () => { beforeEdit = snapshot(); });
    select.addEventListener('change', () => { if (beforeEdit) { history.record(beforeEdit); beforeEdit = null; updateHistoryButtons(); } else recordHistory(); onChange(select.value); renderProfessionalTimeline(); }); wrap.append(label, select); return wrap;
  }

  function defaults(clip) {
    return Object.assign({
      clip_id: crypto.randomUUID(), media_id: null, order: 0, trim_start_seconds: 0, trim_end_seconds: null, volume: 1,
      scene_type: 'video', slot_key: null, slot_title: null, slot_description: null, duration_seconds: 3,
      fade_in_seconds: 0, fade_out_seconds: 0, transition_to_next: 'cut', transition_duration_seconds: .5,
      title_text: null, overlay_text: null, text_position: 'lower_third', font_size: 48, brightness: 0, contrast: 1,
      saturation: 1, exposure: 0, color_temperature: 0, lut_media_id: null,
      logo_media_id: null, logo_fade_in_seconds: 0, logo_fade_out_seconds: 0,
      text_animation: 'none', text_animation_duration_seconds: .5, text_x: .5, text_y: .72,
      requires_verified_lipsync: false, lipsync_verified: false, media: null,
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
    return model.clipDuration(clip);
  }
  function totalDuration() {
    const layout = model.computeLayout(state.clips); return layout.length ? layout.at(-1).end : 0;
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
        selectField('Transition to next', index === state.clips.length - 1 ? 'cut' : clip.transition_to_next, [
          ['cut', 'Cut'], ['crossfade', 'Crossfade'], ['fade_black', 'Fade to black'], ['fade_white', 'Fade to white'],
          ['dissolve', 'Dissolve'], ['slide_left', 'Slide left'], ['slide_right', 'Slide right'], ['zoom', 'Zoom'],
        ], value => { clip.transition_to_next = value; renderDuration(); }),
        field('Transition duration', 'number', clip.transition_duration_seconds, input => { clip.transition_duration_seconds = Number(input.value); renderDuration(); }, {min: .1, max: 3, step: .1, disabled: index === state.clips.length - 1}),
        field('Brightness', 'number', clip.brightness, input => { clip.brightness = Number(input.value); }, {min: -1, max: 1, step: .05}),
        field('Contrast', 'number', clip.contrast, input => { clip.contrast = Number(input.value); }, {min: .5, max: 2, step: .05}),
        field('Saturation', 'number', clip.saturation, input => { clip.saturation = Number(input.value); }, {min: 0, max: 3, step: .05}),
        field('Exposure', 'number', clip.exposure, input => { clip.exposure = Number(input.value); }, {min: -3, max: 3, step: .05}),
        field('Color temperature', 'range', clip.color_temperature, input => { clip.color_temperature = Number(input.value); }, {min: -1, max: 1, step: .05}),
        selectField('Text position', clip.text_position, [['top', 'Top'], ['center', 'Center'], ['lower_third', 'Lower third'], ['custom', 'Custom']], value => { clip.text_position = value; }),
        field('Font size', 'number', clip.font_size, input => { clip.font_size = Number(input.value); }, {min: 12, max: 96, step: 1}),
        field('Custom text X', 'range', clip.text_x, input => { clip.text_x = Number(input.value); }, {min: 0, max: 1, step: .01}),
        field('Custom text Y', 'range', clip.text_y, input => { clip.text_y = Number(input.value); }, {min: 0, max: 1, step: .01}),
        selectField('Text animation', clip.text_animation, [['none', 'None'], ['fade', 'Fade'], ['slide_up', 'Slide up'], ['slide_left', 'Slide left']], value => { clip.text_animation = value; }),
        field('Text animation duration', 'number', clip.text_animation_duration_seconds, input => { clip.text_animation_duration_seconds = Number(input.value); }, {min: .1, max: 3, step: .1}),
        field('Title/card text', 'textarea', clip.title_text || '', input => { clip.title_text = input.value || null; }, {wide: true, maxLength: 200}),
        field('Overlay text', 'textarea', clip.overlay_text || '', input => { clip.overlay_text = input.value || null; }, {wide: true, maxLength: 300}),
      );
      const logoEntries = [['', 'No logo'], ...state.logos.map(logo => [logo.media_id, logo.original_filename])];
      const lutEntries = [['', 'No LUT'], ...state.luts.map(lut => [lut.media_id, lut.original_filename])];
      cinema.append(
        selectField('Logo overlay', clip.logo_media_id || '', logoEntries, value => { clip.logo_media_id = value || null; }),
        field('Logo fade in', 'number', clip.logo_fade_in_seconds, input => { clip.logo_fade_in_seconds = Number(input.value); }, {min: 0, max: 5, step: .1}),
        field('Logo fade out', 'number', clip.logo_fade_out_seconds, input => { clip.logo_fade_out_seconds = Number(input.value); }, {min: 0, max: 5, step: .1}),
        selectField('Color LUT', clip.lut_media_id || '', lutEntries, value => { clip.lut_media_id = value || null; }),
      );
      const resetEffects = button('Reset visual effects', 'secondary');
      resetEffects.addEventListener('click', () => { recordHistory(); Object.assign(clip, {brightness: 0, contrast: 1, saturation: 1, exposure: 0, color_temperature: 0, lut_media_id: null}); renderTimeline(); });
      cinema.append(resetEffects);
      if (clip.scene_type === 'video') {
        const verify = field(clip.requires_verified_lipsync ? 'Required: visible lip-sync verified' : 'Visible lip-sync verified (manual)', 'checkbox', '', input => { clip.lipsync_verified = input.checked; }, {});
        verify.querySelector('input').checked = clip.lipsync_verified; cinema.append(verify);
      }
      body.append(cinema);

      const actions = document.createElement('div'); actions.className = 'timeline-clip-actions';
      const play = button('Preview', 'secondary'); play.addEventListener('click', () => { state.selectedClipId = clip.clip_id; previewScene(index, false); renderProfessionalTimeline(); });
      const up = button('↑', 'secondary'); up.disabled = index === 0; up.addEventListener('click', () => moveClip(index, -1));
      const down = button('↓', 'secondary'); down.disabled = index === state.clips.length - 1; down.addEventListener('click', () => moveClip(index, 1));
      const remove = button('Remove', 'secondary'); remove.addEventListener('click', () => { recordHistory(); state.clips.splice(index, 1); renderTimeline(); });
      actions.append(play, up, down, remove); card.append(body, actions); clipRoot.append(card);
    });
    if (state.clips.length) state.clips[state.clips.length - 1].transition_to_next = 'cut';
    renderDuration(); renderAssignmentTargets(); renderDialogueScenes(); renderProfessionalTimeline(); refreshExportButton();
  }

  function renderDuration() { q('#timeline-duration').textContent = `${Math.max(0, totalDuration()).toFixed(2)} seconds`; }
  function moveClip(index, direction) { const target = index + direction; if (target < 0 || target >= state.clips.length) return; recordHistory(); state.clips = model.reorder(state.clips, index, target); renderTimeline(); }

  function formatTime(seconds) {
    const safe = Math.max(0, Number(seconds) || 0); const minutes = Math.floor(safe / 60);
    return `${String(minutes).padStart(2, '0')}:${(safe % 60).toFixed(2).padStart(5, '0')}`;
  }

  function renderDialogueScenes() {
    const select = q('#timeline-voice-scene'); const current = select.value; select.replaceChildren();
    const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'Whole timeline'; select.append(blank);
    state.clips.forEach((clip, index) => { const option = document.createElement('option'); option.value = clip.clip_id; option.textContent = `${index + 1}. ${clip.slot_title || clip.media?.original_filename || 'Scene'}`; select.append(option); });
    select.value = [...select.options].some(option => option.value === current) ? current : '';
  }

  function renderAudioTrack(kind, root) {
    root.replaceChildren(); const media = state[kind]; if (!media) return;
    const start = Number(q(`#timeline-${kind}-offset`).value || 0) + Number(q(`#timeline-${kind}-sync`).value || 0);
    const sourceStart = kind === 'voice' ? Number(q('#timeline-voice-source-start').value || 0) : 0;
    const sourceEndValue = kind === 'voice' ? q('#timeline-voice-source-end').value : '';
    const sourceEnd = sourceEndValue ? Number(sourceEndValue) : media.duration_seconds;
    const endValue = q(`#timeline-${kind}-end`).value;
    const duration = Math.max(.05, Math.min(sourceEnd - sourceStart, endValue ? Number(endValue) - start : media.duration_seconds));
    const block = document.createElement('div'); block.className = `audio-track-block ${kind}`;
    block.style.left = `${Math.max(0, start) * state.zoom}px`; block.style.width = `${duration * state.zoom}px`;
    if (media.waveform_url) block.style.backgroundImage = `url("${media.waveform_url}")`;
    block.title = `${kind} · ${formatTime(start)} · ${duration.toFixed(2)}s`; root.append(block);
  }

  function renderProfessionalTimeline() {
    const layout = model.computeLayout(state.clips); const duration = Math.max(5, layout.length ? layout.at(-1).end : 0);
    const canvas = q('#timeline-track-canvas'); const contentWidth = Math.ceil(duration * state.zoom); canvas.style.width = `${contentWidth + 74}px`;
    q('#timeline-zoom').value = state.zoom;
    const ruler = q('#timeline-ruler'); ruler.replaceChildren(); ruler.style.width = `${contentWidth}px`;
    const interval = state.zoom >= 120 ? .5 : state.zoom >= 50 ? 1 : 5;
    for (let second = 0; second <= duration + .001; second += interval) {
      const mark = document.createElement('span'); mark.className = 'ruler-mark'; mark.style.left = `${second * state.zoom}px`; mark.textContent = interval < 1 ? second.toFixed(1) : formatTime(second).slice(0, 5); ruler.append(mark);
    }
    const videoTrack = q('#timeline-video-track'); videoTrack.replaceChildren(); videoTrack.style.width = `${contentWidth}px`;
    layout.forEach(entry => {
      const clip = state.clips[entry.index]; const block = document.createElement('div'); block.className = `timeline-track-clip${state.selectedClipId === clip.clip_id ? ' selected' : ''}`;
      block.style.left = `${entry.start * state.zoom}px`; block.style.width = `${Math.max(18, entry.duration * state.zoom)}px`; block.dataset.index = String(entry.index); block.tabIndex = 0;
      if (clip.media?.thumbnail_url) { const image = document.createElement('img'); image.src = clip.media.thumbnail_url; image.alt = ''; block.append(image); }
      const label = document.createElement('span'); label.textContent = clip.slot_title || clip.media?.original_filename || clip.title_text || 'Planned'; block.append(label);
      let pointerStart = null;
      block.addEventListener('pointerdown', event => { if (event.button !== 0) return; state.selectedClipId = clip.clip_id; pointerStart = {x: event.clientX, index: entry.index}; block.setPointerCapture(event.pointerId); videoTrack.querySelectorAll('.selected').forEach(item => item.classList.remove('selected')); block.classList.add('selected'); });
      block.addEventListener('pointerup', event => {
        if (!pointerStart) return; const delta = event.clientX - pointerStart.x;
        if (Math.abs(delta) > 8) {
          const rect = videoTrack.getBoundingClientRect(); const targetTime = (event.clientX - rect.left) / state.zoom;
          let target = layout.findIndex(item => targetTime < item.start + item.duration / 2); if (target < 0) target = state.clips.length - 1;
          recordHistory(); state.clips = model.reorder(state.clips, pointerStart.index, target); renderTimeline();
        }
        pointerStart = null;
      });
      videoTrack.append(block);
    });
    renderAudioTrack('voice', q('#timeline-voice-track')); renderAudioTrack('music', q('#timeline-music-track'));
    setPlayhead(state.playhead, false); updateHistoryButtons();
  }

  function setPlayhead(seconds, seek = true) {
    state.playhead = Math.max(0, Math.min(Number(seconds) || 0, totalDuration()));
    q('#timeline-playhead').style.left = `${74 + state.playhead * state.zoom}px`; q('#timeline-playhead-time').textContent = formatTime(state.playhead);
    if (!seek) return;
    const layout = model.computeLayout(state.clips); const entry = layout.find(item => state.playhead >= item.start && state.playhead <= item.end);
    if (entry) previewScene(entry.index, false, false, state.playhead - entry.start);
  }

  function splitAtPlayhead() {
    const previousIds = new Set(state.clips.map(clip => clip.clip_id));
    const result = model.splitAt(state.clips, state.playhead);
    if (!result) { message('Move the playhead inside a scene before splitting.', 'warning'); return; }
    recordHistory(); state.clips = result; state.selectedClipId = result.find(clip => !previousIds.has(clip.clip_id))?.clip_id || null; renderTimeline(); message('Scene split non-destructively at the playhead.', 'success');
  }
  function hidePreviews() {
    clearTimeout(state.previewTimer); videoPreview.pause(); q('#timeline-preview-voice').pause(); q('#timeline-preview-music').pause();
    videoPreview.classList.add('hidden'); imagePreview.classList.add('hidden'); cardPreview.classList.add('hidden');
    q('#timeline-preview-logo').classList.add('hidden'); q('#timeline-preview-text').classList.add('hidden');
  }

  function applyPreviewVisuals(clip, index) {
    const stage = q('#timeline-preview-stage');
    const exposure = 2 ** Number(clip.exposure || 0); const warmth = Number(clip.color_temperature || 0);
    stage.style.filter = `brightness(${Math.max(0, (1 + Number(clip.brightness || 0)) * exposure)}) contrast(${clip.contrast}) saturate(${clip.saturation}) sepia(${Math.abs(warmth) * .22}) hue-rotate(${warmth * -12}deg)`;
    stage.className = 'timeline-preview-stage'; const previous = index > 0 ? state.clips[index - 1].transition_to_next : 'cut'; if (previous !== 'cut') stage.classList.add(`approx-${previous}`);
    const logo = state.logos.find(item => item.media_id === clip.logo_media_id); const logoElement = q('#timeline-preview-logo');
    if (logo) { logoElement.src = logo.preview_url; logoElement.classList.remove('hidden'); logoElement.style.animation = clip.logo_fade_in_seconds ? `preview-fade ${clip.logo_fade_in_seconds}s ease both` : ''; }
    const text = clip.overlay_text || (clip.scene_type === 'video' || clip.scene_type === 'still' ? clip.title_text : null); const textElement = q('#timeline-preview-text');
    if (text) {
      textElement.textContent = text; textElement.className = `preview-text ${clip.text_position} animate-${clip.text_animation}`;
      textElement.style.setProperty('--text-x', `${clip.text_x * 100}%`); textElement.style.setProperty('--text-y', `${clip.text_y * 100}%`); textElement.style.fontSize = `${Math.max(12, clip.font_size) / 32}rem`;
    }
  }

  function syncPreviewAudio(timelineTime, autoplay) {
    const duck = q('#timeline-ducking-enabled').checked && state.voice;
    ['voice', 'music'].forEach(kind => {
      const media = state[kind]; const element = q(`#timeline-preview-${kind}`); if (!media) { element.pause(); return; }
      const start = Number(q(`#timeline-${kind}-offset`).value || 0) + Number(q(`#timeline-${kind}-sync`).value || 0);
      const endValue = q(`#timeline-${kind}-end`).value; const end = endValue ? Number(endValue) : start + media.duration_seconds;
      if (timelineTime < start || timelineTime >= end) { element.pause(); return; }
      const sourceStart = kind === 'voice' ? Number(q('#timeline-voice-source-start').value || 0) : 0;
      element.src = media.preview_url; element.currentTime = Math.max(0, sourceStart + timelineTime - start);
      let volume = Math.min(1, Number(q(`#timeline-${kind}-volume`).value));
      if (kind === 'music' && duck) volume *= 1 - Number(q('#timeline-ducking-intensity').value) * .7;
      element.volume = volume; if (autoplay) element.play().catch(() => {});
    });
  }

  function previewScene(index, sequence, autoplay = true, offset = 0) {
    const clip = state.clips[index]; hidePreviews();
    if (!clip) { message('Available-scene sequence preview completed.', 'success'); return; }
    applyPreviewVisuals(clip, index); const layout = model.computeLayout(state.clips); const timelineStart = layout[index]?.start || 0; state.playhead = timelineStart + offset; setPlayhead(state.playhead, false); syncPreviewAudio(state.playhead, autoplay);
    const next = () => { if (sequence) previewScene(index + 1, true); };
    if (clip.scene_type === 'video' && clip.media) {
      videoPreview.classList.remove('hidden'); videoPreview.src = clip.media.preview_url; videoPreview.load();
      videoPreview.onloadedmetadata = () => { videoPreview.currentTime = Number(clip.trim_start_seconds) + offset; if (autoplay) videoPreview.play().catch(() => message('Select play to continue the preview.', 'warning')); };
      videoPreview.ontimeupdate = () => { setPlayhead(timelineStart + Math.max(0, videoPreview.currentTime - Number(clip.trim_start_seconds)), false); if (videoPreview.currentTime >= Number(clip.trim_end_seconds ?? clip.media.duration_seconds) - .03) { videoPreview.pause(); next(); } };
    } else if (clip.scene_type === 'still' && clip.media) {
      imagePreview.src = clip.media.preview_url; imagePreview.classList.remove('hidden'); if (sequence && autoplay) state.previewTimer = setTimeout(next, Math.max(0, clip.duration_seconds - offset) * 1000);
    } else if (['title_card', 'branding_card'].includes(clip.scene_type)) {
      cardPreview.textContent = clip.title_text || ''; cardPreview.classList.remove('hidden'); if (sequence && autoplay) state.previewTimer = setTimeout(next, Math.max(0, clip.duration_seconds - offset) * 1000);
    } else { message(`Scene ${index + 1} remains planned and was skipped.`, 'warning'); if (sequence) state.previewTimer = setTimeout(next, 250); }
  }

  async function uploadMedia(file, kind) { const form = new FormData(); form.set('kind', kind); form.set('media', file); return json(await fetch('/api/timeline/media', {method: 'POST', body: form})); }
  function assignMedia(media, sceneType) {
    recordHistory();
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
    try { const logo = await uploadMedia(file, 'logo'); recordHistory(); state.logos.push(logo); q('#timeline-logo-name').textContent = logo.original_filename; q('#timeline-logo-input').value = ''; renderTimeline(); message('Logo preserved for explicit scene overlays.', 'success'); }
    catch (error) { message(error.message, 'error'); }
  }

  async function uploadLut() {
    const file = q('#timeline-lut-input').files[0]; if (!file) { message('Choose a .cube LUT first.', 'warning'); return; }
    try { const lut = await uploadMedia(file, 'lut'); recordHistory(); state.luts.push(lut); q('#timeline-lut-name').textContent = lut.original_filename; q('#timeline-lut-input').value = ''; renderTimeline(); message('Validated LUT preserved locally.', 'success'); }
    catch (error) { message(error.message, 'error'); }
  }

  function optionalNumber(selector) { const value = q(selector).value; return value === '' ? null : Number(value); }
  function trackDraft(kind) {
    const media = state[kind]; if (!media) return null;
    return {
      media_id: media.media_id, volume: Number(q(`#timeline-${kind}-volume`).value), start_seconds: Number(q(`#timeline-${kind}-offset`).value),
      end_seconds: optionalNumber(`#timeline-${kind}-end`), source_start_seconds: kind === 'voice' ? Number(q('#timeline-voice-source-start').value) : 0,
      source_end_seconds: kind === 'voice' ? optionalNumber('#timeline-voice-source-end') : null,
      sync_offset_seconds: Number(q(`#timeline-${kind}-sync`).value), fade_in_seconds: Number(q(`#timeline-${kind}-fade-in`).value),
      fade_out_seconds: Number(q(`#timeline-${kind}-fade-out`).value), scene_clip_id: kind === 'voice' ? q('#timeline-voice-scene').value || null : null,
    };
  }

  function projectDraft() {
    normalizeOrders();
    return {
      schema_version: '1.2', name: q('#timeline-project-name').value.trim() || 'Untitled advertisement', project_kind: state.projectKind,
      template_id: state.templateId, clips: state.clips.map(({media, ...clip}) => clip),
      voice_track: trackDraft('voice'), music_track: trackDraft('music'),
      ducking_enabled: q('#timeline-ducking-enabled').checked, ducking_intensity: Number(q('#timeline-ducking-intensity').value),
      timeline_zoom: state.zoom, playhead_seconds: state.playhead,
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
      const lutIds = [...new Set(project.clips.map(clip => clip.lut_media_id).filter(Boolean))]; state.luts = await Promise.all(lutIds.map(async idValue => json(await fetch(`/api/timeline/media/${idValue}`))));
      state.selectedCharacters = new Set(project.character_reference_ids || []); q('#timeline-project-name').value = project.name; q('#timeline-profile').value = project.export_profile;
      setTrackInputs('voice', project.voice_track, 1); setTrackInputs('music', project.music_track, .35);
      q('#timeline-ducking-enabled').checked = project.ducking_enabled ?? true; q('#timeline-ducking-intensity').value = project.ducking_intensity ?? .55;
      state.zoom = project.timeline_zoom ?? 80; state.playhead = project.playhead_seconds ?? 0; q('#timeline-zoom').value = state.zoom;
      renderAudio(); await loadCharacters(); renderTimeline(); q('#timeline-voice-scene').value = project.voice_track?.scene_clip_id ?? ''; history.clear(); updateHistoryButtons(); message(`Opened ${project.name}.`, 'success');
    } catch (error) { message(error.message, 'error'); }
  }
  function newProject() {
    hidePreviews(); state.clips = []; state.projectId = null; state.projectKind = 'timeline'; state.templateId = null; state.voice = null; state.music = null; state.logos = []; state.luts = []; state.selectedCharacters = new Set(); state.playhead = 0; state.zoom = 80;
    q('#timeline-project-name').value = 'Untitled project'; q('#timeline-profile').value = '720p'; q('#timeline-projects').value = ''; setTrackInputs('voice', null, 1); setTrackInputs('music', null, .35); q('#timeline-ducking-enabled').checked = true; q('#timeline-ducking-intensity').value = .55; history.clear(); renderAudio(); renderTimeline(); loadCharacters().catch(error => message(error.message, 'error')); message('Started a new local project.');
  }
  async function loadWoodoraTemplate() {
    try { const data = await json(await fetch('/api/timeline/templates/woodora-grand-arrival')); const project = data.project; state.clips = project.clips.map(defaults); state.projectId = null; state.projectKind = project.project_kind; state.templateId = project.template_id; state.voice = null; state.music = null; state.logos = []; state.luts = []; state.selectedCharacters = new Set(); state.characterTemplates = data.character_templates; q('#timeline-project-name').value = project.name; fillCharacterTemplates(); history.clear(); renderAudio(); await loadCharacters(); renderTimeline(); message(data.warning, 'warning'); }
    catch (error) { message(error.message, 'error'); }
  }
  function addCard(type) { recordHistory(); state.clips.push(defaults({order: state.clips.length, scene_type: type, duration_seconds: 3, title_text: type === 'branding_card' ? 'BRAND' : 'Opening title'})); state.projectKind = 'advertisement'; renderTimeline(); }

  function setTrackInputs(kind, track, defaultVolume) {
    q(`#timeline-${kind}-volume`).value = track?.volume ?? defaultVolume; q(`#timeline-${kind}-offset`).value = track?.start_seconds ?? 0;
    q(`#timeline-${kind}-sync`).value = track?.sync_offset_seconds ?? 0; q(`#timeline-${kind}-end`).value = track?.end_seconds ?? '';
    q(`#timeline-${kind}-fade-in`).value = track?.fade_in_seconds ?? 0; q(`#timeline-${kind}-fade-out`).value = track?.fade_out_seconds ?? 0;
    if (kind === 'voice') { q('#timeline-voice-source-start').value = track?.source_start_seconds ?? 0; q('#timeline-voice-source-end').value = track?.source_end_seconds ?? ''; }
  }
  function renderAudio() {
    q('#timeline-voice-name').textContent = state.voice?.original_filename || 'No voice track.'; q('#timeline-music-name').textContent = state.music?.original_filename || 'No music track.';
    q('#timeline-voice-volume-label').textContent = `${Math.round(Number(q('#timeline-voice-volume').value) * 100)}%`; q('#timeline-music-volume-label').textContent = `${Math.round(Number(q('#timeline-music-volume').value) * 100)}%`;
    q('#timeline-ducking-label').textContent = `${Math.round(Number(q('#timeline-ducking-intensity').value) * 100)}%`; renderProfessionalTimeline();
  }
  async function selectAudio(event, kind) { const file = event.target.files[0]; if (!file) return; try { const media = await uploadMedia(file, kind); recordHistory(); state[kind] = media; renderAudio(); message(`${kind === 'voice' ? 'Malayalam voice' : 'Background music'} preserved locally with a local waveform.`, 'success'); } catch (error) { message(error.message, 'error'); event.target.value = ''; } }

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

  async function pollExport(jobId, renderedPreview = false) { clearTimeout(state.exportTimer); try { const job = await json(await fetch(`/api/timeline/exports/${jobId}`)); exportState(job.state, job.error || job.message, job.state === 'COMPLETED' ? 'completed' : job.state === 'FAILED' ? 'failed' : ''); if (job.state === 'COMPLETED') { const url = `/api/timeline/exports/${jobId}/output`; q('#timeline-export-player').src = url; q('#timeline-export-download').href = url; q('#timeline-export-result').classList.remove('hidden'); message(renderedPreview ? 'Rendered preview is export-accurate for the saved project.' : 'Final export passed independent FFprobe verification.', 'success'); refreshExportButton(); } else if (job.state === 'FAILED') refreshExportButton(); else state.exportTimer = setTimeout(() => pollExport(jobId, renderedPreview), 1000); } catch (error) { exportState('FAILED', error.message, 'failed'); refreshExportButton(); } }
  async function startRender(endpoint, renderedPreview) { exportButton.disabled = true; q('#timeline-export-result').classList.add('hidden'); try { const project = await saveProject(); exportState('QUEUED', renderedPreview ? 'Rendering an export-accurate local preview.' : 'Submitting the saved project to local FFmpeg.'); const job = await json(await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project_id: project.project_id})})); pollExport(job.job_id, renderedPreview); } catch (error) { exportState('FAILED', error.message, 'failed'); refreshExportButton(); } }
  async function startExport() { return startRender('/api/timeline/exports', false); }
  async function startRenderedPreview() { return startRender('/api/timeline/previews', true); }
  async function loadCapabilities() { try { const data = await json(await fetch('/api/timeline/capabilities')); state.capabilities = data; q('#timeline-availability').textContent = data.ffmpeg_available && data.ffprobe_available && data.safe_font_available ? 'FFmpeg + safe font ready' : 'Local tools incomplete'; const generated = q('#timeline-generated-clips'); generated.replaceChildren(); const blank = document.createElement('option'); blank.value = ''; blank.textContent = data.generated_job_ids.length ? 'Choose a generated clip' : 'No generated clips detected'; generated.append(blank); data.generated_job_ids.forEach(id => { const option = document.createElement('option'); option.value = id; option.textContent = id; generated.append(option); }); const templates = await json(await fetch('/api/timeline/character-templates')); state.characterTemplates = templates.templates; fillCharacterTemplates(); await Promise.all([loadProjectList(), loadCharacters()]); refreshExportButton(); } catch (error) { message(error.message, 'error'); exportState('UNAVAILABLE', error.message, 'unavailable'); } }

  q('#timeline-upload-clips').addEventListener('click', () => addFiles('#timeline-clip-input', 'clip', 'video'));
  q('#timeline-upload-images').addEventListener('click', () => addFiles('#timeline-image-input', 'image', 'still'));
  q('#timeline-upload-logo').addEventListener('click', uploadLogo); q('#timeline-upload-lut').addEventListener('click', uploadLut); q('#timeline-import-generated').addEventListener('click', importGenerated);
  q('#timeline-play-sequence').addEventListener('click', () => previewScene(0, true)); q('#timeline-save-project').addEventListener('click', () => saveProject().catch(error => message(error.message, 'error')));
  q('#timeline-open-project').addEventListener('click', loadProject); q('#timeline-new-project').addEventListener('click', newProject); q('#timeline-load-woodora').addEventListener('click', loadWoodoraTemplate);
  q('#timeline-add-title').addEventListener('click', () => addCard('title_card')); q('#timeline-add-brand').addEventListener('click', () => addCard('branding_card')); q('#timeline-export').addEventListener('click', startExport);
  q('#timeline-render-preview').addEventListener('click', startRenderedPreview); q('#timeline-undo').addEventListener('click', undo); q('#timeline-redo').addEventListener('click', redo); q('#timeline-split').addEventListener('click', splitAtPlayhead);
  q('#timeline-voice-input').addEventListener('change', event => selectAudio(event, 'voice')); q('#timeline-music-input').addEventListener('change', event => selectAudio(event, 'music'));
  ['voice', 'music'].forEach(kind => q(`#timeline-${kind}-volume`).addEventListener('input', renderAudio));
  ['voice', 'music'].forEach(kind => ['offset', 'sync', 'end', 'fade-in', 'fade-out'].forEach(name => q(`#timeline-${kind}-${name}`).addEventListener('change', () => { renderAudio(); markDirty(); })));
  ['#timeline-voice-source-start', '#timeline-voice-source-end'].forEach(selector => q(selector).addEventListener('change', renderAudio));
  q('#timeline-ducking-intensity').addEventListener('input', renderAudio); q('#timeline-ducking-enabled').addEventListener('change', renderAudio);
  q('#timeline-voice-scene').addEventListener('change', () => { recordHistory(); const entry = model.computeLayout(state.clips).find(item => item.clip_id === q('#timeline-voice-scene').value); if (entry) { q('#timeline-voice-offset').value = entry.start.toFixed(2); q('#timeline-voice-sync').value = 0; } renderAudio(); });
  q('#timeline-zoom').addEventListener('input', event => { state.zoom = Number(event.target.value); renderProfessionalTimeline(); });
  q('#timeline-ruler').addEventListener('pointerdown', event => { const rect = q('#timeline-ruler').getBoundingClientRect(); setPlayhead((event.clientX - rect.left) / state.zoom); });
  q('#timeline-track-canvas').addEventListener('pointerdown', event => { if (event.target.closest('.timeline-track-clip') || event.target.closest('.audio-track-block') || event.target.closest('#timeline-ruler')) return; const rect = q('#timeline-video-track').getBoundingClientRect(); setPlayhead((event.clientX - rect.left) / state.zoom); });
  q('#timeline-character-template').addEventListener('change', applyCharacterTemplate); q('#timeline-save-character').addEventListener('click', saveCharacter);
  [
    '#timeline-voice-volume', '#timeline-voice-offset', '#timeline-voice-sync', '#timeline-voice-end', '#timeline-voice-source-start', '#timeline-voice-source-end', '#timeline-voice-fade-in', '#timeline-voice-fade-out',
    '#timeline-music-volume', '#timeline-music-offset', '#timeline-music-sync', '#timeline-music-end', '#timeline-music-fade-in', '#timeline-music-fade-out', '#timeline-ducking-enabled', '#timeline-ducking-intensity', '#timeline-zoom',
  ].forEach(selector => {
    const input = q(selector); let before = null; input.addEventListener('focus', () => { before = snapshot(); });
    input.addEventListener('change', () => { if (before) { history.record(before); before = null; updateHistoryButtons(); } });
  });
  document.addEventListener('keydown', event => {
    if (event.target.matches('input,textarea,select')) return;
    const modifier = event.ctrlKey || event.metaKey;
    if (modifier && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); return; }
    if (modifier && event.key.toLowerCase() === 'y') { event.preventDefault(); redo(); return; }
    if (event.code === 'Space') { event.preventDefault(); if (!videoPreview.classList.contains('hidden')) videoPreview.paused ? videoPreview.play() : videoPreview.pause(); else setPlayhead(state.playhead); return; }
    if (event.key.toLowerCase() === 's') { event.preventDefault(); splitAtPlayhead(); return; }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); setPlayhead(state.playhead + (event.key === 'ArrowRight' ? .1 : -.1)); return; }
    if ((event.key === 'Delete' || event.key === 'Backspace') && state.selectedClipId) { const index = state.clips.findIndex(clip => clip.clip_id === state.selectedClipId); if (index >= 0) { recordHistory(); state.clips.splice(index, 1); state.selectedClipId = null; renderTimeline(); } }
  });
  renderTimeline(); renderAudio(); loadCapabilities();
})();
