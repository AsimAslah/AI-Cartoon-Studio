(() => {
  const timelineState = {
    clips: [],
    projectId: null,
    voice: null,
    music: null,
    projects: [],
    capabilities: null,
    dirty: true,
    exportTimer: null,
  };

  const clipRoot = document.querySelector('#timeline-clips');
  const preview = document.querySelector('#timeline-preview');
  const exportButton = document.querySelector('#timeline-export');

  async function timelineJson(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Timeline request failed.';
      throw new Error(detail);
    }
    return data;
  }

  function timelineMessage(text, kind = 'notice') {
    const root = document.querySelector('#timeline-message');
    root.textContent = text;
    root.className = kind;
  }

  function exportState(stage, text, kind = '') {
    const root = document.querySelector('#timeline-export-state');
    root.className = `render-state ${kind || stage.toLowerCase()}`;
    root.replaceChildren();
    const strong = document.createElement('strong'); strong.textContent = stage.replaceAll('_', ' ');
    const span = document.createElement('span'); span.textContent = text;
    root.append(strong, span);
  }

  function normalizeOrders() {
    timelineState.clips.forEach((clip, index) => { clip.order = index; });
  }

  function markDirty() {
    timelineState.dirty = true;
    refreshExportButton();
  }

  function clipEnd(clip) {
    return Number(clip.trim_end_seconds ?? clip.media.duration_seconds);
  }

  function totalDuration() {
    return timelineState.clips.reduce((total, clip) => total + Math.max(0, clipEnd(clip) - Number(clip.trim_start_seconds)), 0);
  }

  function refreshExportButton() {
    const available = timelineState.capabilities?.ffmpeg_available && timelineState.capabilities?.ffprobe_available;
    exportButton.disabled = !(available && timelineState.clips.length);
  }

  function button(text, className = '') {
    const element = document.createElement('button');
    element.type = 'button'; element.textContent = text; element.className = className;
    return element;
  }

  function numberField(labelText, value, min, max, onChange) {
    const wrapper = document.createElement('div');
    const label = document.createElement('label'); label.textContent = labelText;
    const input = document.createElement('input');
    input.type = 'number'; input.step = '0.01'; input.min = String(min); input.max = String(max); input.value = Number(value).toFixed(2);
    input.addEventListener('change', () => onChange(Number(input.value), input));
    wrapper.append(label, input);
    return wrapper;
  }

  function renderTimeline() {
    normalizeOrders();
    clipRoot.replaceChildren();
    if (!timelineState.clips.length) {
      const empty = document.createElement('p'); empty.className = 'muted'; empty.textContent = 'No clips yet.';
      clipRoot.append(empty);
    }
    timelineState.clips.forEach((clip, index) => {
      const card = document.createElement('article'); card.className = 'timeline-clip';
      const image = document.createElement('img'); image.src = clip.media.thumbnail_url; image.alt = `Thumbnail for ${clip.media.original_filename}`;
      const body = document.createElement('div');
      const title = document.createElement('h4'); title.textContent = `${index + 1}. ${clip.media.original_filename}`;
      const details = document.createElement('small');
      details.textContent = `${clip.media.width}×${clip.media.height} · ${Number(clip.media.duration_seconds).toFixed(2)}s · ${clip.media.codec}`;
      const fields = document.createElement('div'); fields.className = 'timeline-clip-fields';
      fields.append(
        numberField('Trim start (s)', clip.trim_start_seconds, 0, clip.media.duration_seconds, (value, input) => {
          const end = clipEnd(clip);
          clip.trim_start_seconds = Math.max(0, Math.min(Number.isFinite(value) ? value : 0, end - 0.01));
          input.value = clip.trim_start_seconds.toFixed(2); markDirty(); renderDuration();
        }),
        numberField('Trim end (s)', clipEnd(clip), 0.01, clip.media.duration_seconds, (value, input) => {
          const start = Number(clip.trim_start_seconds);
          clip.trim_end_seconds = Math.max(start + 0.01, Math.min(Number.isFinite(value) ? value : clip.media.duration_seconds, clip.media.duration_seconds));
          input.value = clip.trim_end_seconds.toFixed(2); markDirty(); renderDuration();
        }),
      );
      const volumeWrap = document.createElement('div');
      const volumeLabel = document.createElement('label'); volumeLabel.textContent = `Clip volume ${Math.round(clip.volume * 100)}%`;
      const volume = document.createElement('input'); volume.type = 'range'; volume.min = '0'; volume.max = '2'; volume.step = '0.05'; volume.value = clip.volume;
      volume.addEventListener('input', () => { clip.volume = Number(volume.value); volumeLabel.textContent = `Clip volume ${Math.round(clip.volume * 100)}%`; markDirty(); });
      volumeWrap.append(volumeLabel, volume); fields.append(volumeWrap);
      body.append(title, details, fields);

      const actions = document.createElement('div'); actions.className = 'timeline-clip-actions';
      const play = button('Preview', 'secondary'); play.addEventListener('click', () => playTimelineClip(index, false));
      const up = button('↑', 'secondary'); up.disabled = index === 0; up.addEventListener('click', () => moveClip(index, -1));
      const down = button('↓', 'secondary'); down.disabled = index === timelineState.clips.length - 1; down.addEventListener('click', () => moveClip(index, 1));
      const remove = button('Remove', 'secondary'); remove.addEventListener('click', () => { timelineState.clips.splice(index, 1); markDirty(); renderTimeline(); });
      actions.append(play, up, down, remove);
      card.append(image, body, actions); clipRoot.append(card);
    });
    renderDuration(); refreshExportButton();
  }

  function renderDuration() {
    document.querySelector('#timeline-duration').textContent = `${totalDuration().toFixed(2)} seconds`;
  }

  function moveClip(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= timelineState.clips.length) return;
    [timelineState.clips[index], timelineState.clips[target]] = [timelineState.clips[target], timelineState.clips[index]];
    markDirty(); renderTimeline();
  }

  function playTimelineClip(index, sequence) {
    const clip = timelineState.clips[index];
    if (!clip) { timelineMessage('Timeline sequence preview completed.', 'success'); return; }
    preview.pause(); preview.src = clip.media.preview_url; preview.load();
    preview.onloadedmetadata = () => {
      preview.currentTime = Number(clip.trim_start_seconds);
      preview.play().catch(() => timelineMessage('Select play in the preview to continue.', 'warning'));
    };
    preview.ontimeupdate = () => {
      if (preview.currentTime >= clipEnd(clip) - 0.03) {
        preview.pause();
        if (sequence) playTimelineClip(index + 1, true);
      }
    };
    timelineMessage(sequence ? `Previewing clip ${index + 1} of ${timelineState.clips.length}.` : `Previewing ${clip.media.original_filename}.`);
  }

  async function uploadMedia(file, kind) {
    const form = new FormData(); form.set('kind', kind); form.set('media', file);
    return timelineJson(await fetch('/api/timeline/media', {method: 'POST', body: form}));
  }

  async function addSelectedClips() {
    const input = document.querySelector('#timeline-clip-input');
    const files = [...input.files];
    if (!files.length) { timelineMessage('Choose one or more MP4 clips first.', 'warning'); return; }
    const trigger = document.querySelector('#timeline-upload-clips'); trigger.disabled = true;
    try {
      for (let index = 0; index < files.length; index += 1) {
        timelineMessage(`Validating and preserving clip ${index + 1} of ${files.length}.`);
        const media = await uploadMedia(files[index], 'clip');
        timelineState.clips.push({
          clip_id: crypto.randomUUID(), media_id: media.media_id, order: timelineState.clips.length,
          trim_start_seconds: 0, trim_end_seconds: media.duration_seconds, volume: 1, media,
        });
      }
      input.value = ''; markDirty(); renderTimeline(); timelineMessage(`${files.length} clip(s) added and preserved locally.`, 'success');
    } catch (error) { timelineMessage(error.message, 'error'); }
    finally { trigger.disabled = false; }
  }

  async function importGeneratedClip() {
    const select = document.querySelector('#timeline-generated-clips');
    if (!select.value) { timelineMessage('Choose a generated clip first.', 'warning'); return; }
    try {
      timelineMessage('Copying and validating the preserved generated clip.');
      const media = await timelineJson(await fetch('/api/timeline/import-generated', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job_id: select.value}),
      }));
      timelineState.clips.push({
        clip_id: crypto.randomUUID(), media_id: media.media_id, order: timelineState.clips.length,
        trim_start_seconds: 0, trim_end_seconds: media.duration_seconds, volume: 1, media,
      });
      markDirty(); renderTimeline(); timelineMessage('Generated clip imported without changing its original file.', 'success');
    } catch (error) { timelineMessage(error.message, 'error'); }
  }

  function projectDraft() {
    normalizeOrders();
    return {
      schema_version: '1.0',
      name: document.querySelector('#timeline-project-name').value.trim() || 'Untitled timeline',
      clips: timelineState.clips.map(({media, ...clip}) => clip),
      voice_track: timelineState.voice ? {media_id: timelineState.voice.media_id, volume: Number(document.querySelector('#timeline-voice-volume').value), start_seconds: 0} : null,
      music_track: timelineState.music ? {media_id: timelineState.music.media_id, volume: Number(document.querySelector('#timeline-music-volume').value), start_seconds: 0} : null,
      export_profile: document.querySelector('#timeline-profile').value,
    };
  }

  async function saveProject() {
    const method = timelineState.projectId ? 'PUT' : 'POST';
    const url = timelineState.projectId ? `/api/timeline/projects/${timelineState.projectId}` : '/api/timeline/projects';
    const project = await timelineJson(await fetch(url, {
      method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(projectDraft()),
    }));
    timelineState.projectId = project.project_id; timelineState.dirty = false;
    await loadProjectList(project.project_id);
    timelineMessage(`Saved timeline project ${project.name}.`, 'success');
    refreshExportButton(); return project;
  }

  async function loadProjectList(selected = timelineState.projectId) {
    const data = await timelineJson(await fetch('/api/timeline/projects'));
    timelineState.projects = data.projects;
    const select = document.querySelector('#timeline-projects');
    select.replaceChildren();
    const blank = document.createElement('option'); blank.value = ''; blank.textContent = 'New unsaved project'; select.append(blank);
    data.projects.forEach(project => {
      const option = document.createElement('option'); option.value = project.project_id;
      option.textContent = `${project.name} · ${project.clip_count} clips`; select.append(option);
    });
    select.value = selected || '';
  }

  async function loadProject() {
    const id = document.querySelector('#timeline-projects').value;
    if (!id) { newProject(); return; }
    try {
      const project = await timelineJson(await fetch(`/api/timeline/projects/${id}`));
      const clips = await Promise.all(project.clips.map(async clip => ({...clip, media: await timelineJson(await fetch(`/api/timeline/media/${clip.media_id}`))})));
      timelineState.clips = clips; timelineState.projectId = project.project_id;
      timelineState.voice = project.voice_track ? await timelineJson(await fetch(`/api/timeline/media/${project.voice_track.media_id}`)) : null;
      timelineState.music = project.music_track ? await timelineJson(await fetch(`/api/timeline/media/${project.music_track.media_id}`)) : null;
      document.querySelector('#timeline-project-name').value = project.name;
      document.querySelector('#timeline-profile').value = project.export_profile;
      if (project.voice_track) document.querySelector('#timeline-voice-volume').value = project.voice_track.volume;
      if (project.music_track) document.querySelector('#timeline-music-volume').value = project.music_track.volume;
      renderAudioNames(); timelineState.dirty = false; renderTimeline();
      timelineMessage(`Opened ${project.name}.`, 'success');
    } catch (error) { timelineMessage(error.message, 'error'); }
  }

  function newProject() {
    preview.pause(); preview.removeAttribute('src'); preview.load();
    timelineState.clips = []; timelineState.projectId = null; timelineState.voice = null; timelineState.music = null; timelineState.dirty = true;
    document.querySelector('#timeline-project-name').value = 'WOODORA advertisement';
    document.querySelector('#timeline-profile').value = '720p';
    document.querySelector('#timeline-projects').value = '';
    document.querySelector('#timeline-voice-input').value = ''; document.querySelector('#timeline-music-input').value = '';
    renderAudioNames(); renderTimeline(); timelineMessage('Started a new unsaved timeline project.');
  }

  function renderAudioNames() {
    document.querySelector('#timeline-voice-name').textContent = timelineState.voice ? timelineState.voice.original_filename : 'No voice track.';
    document.querySelector('#timeline-music-name').textContent = timelineState.music ? timelineState.music.original_filename : 'No music track.';
    document.querySelector('#timeline-voice-volume-label').textContent = `${Math.round(Number(document.querySelector('#timeline-voice-volume').value) * 100)}%`;
    document.querySelector('#timeline-music-volume-label').textContent = `${Math.round(Number(document.querySelector('#timeline-music-volume').value) * 100)}%`;
  }

  async function selectAudio(event, kind) {
    const file = event.target.files[0]; if (!file) return;
    try {
      timelineMessage(`Validating and preserving ${kind} audio.`);
      const media = await uploadMedia(file, kind);
      timelineState[kind] = media; markDirty(); renderAudioNames();
      timelineMessage(`${kind === 'voice' ? 'Malayalam voice' : 'Background music'} added locally.`, 'success');
    } catch (error) { timelineMessage(error.message, 'error'); event.target.value = ''; }
  }

  async function pollExport(jobId) {
    clearTimeout(timelineState.exportTimer);
    try {
      const job = await timelineJson(await fetch(`/api/timeline/exports/${jobId}`));
      exportState(job.state, job.error || job.message, job.state === 'COMPLETED' ? 'completed' : job.state === 'FAILED' ? 'failed' : '');
      if (job.state === 'COMPLETED') {
        const url = `/api/timeline/exports/${jobId}/output`;
        document.querySelector('#timeline-export-player').src = url;
        document.querySelector('#timeline-export-download').href = url;
        document.querySelector('#timeline-export-result').classList.remove('hidden');
        exportButton.disabled = false;
      } else if (job.state === 'FAILED') exportButton.disabled = false;
      else timelineState.exportTimer = setTimeout(() => pollExport(jobId), 1000);
    } catch (error) { exportState('FAILED', error.message, 'failed'); exportButton.disabled = false; }
  }

  async function startExport() {
    exportButton.disabled = true; document.querySelector('#timeline-export-result').classList.add('hidden');
    try {
      const project = await saveProject();
      exportState('QUEUED', 'Submitting the saved project to the local FFmpeg worker.');
      const job = await timelineJson(await fetch('/api/timeline/exports', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project_id: project.project_id}),
      }));
      pollExport(job.job_id);
    } catch (error) { exportState('FAILED', error.message, 'failed'); refreshExportButton(); }
  }

  async function loadCapabilities() {
    try {
      const data = await timelineJson(await fetch('/api/timeline/capabilities'));
      timelineState.capabilities = data;
      document.querySelector('#timeline-availability').textContent = data.ffmpeg_available && data.ffprobe_available ? 'FFmpeg ready' : 'FFmpeg unavailable';
      const generated = document.querySelector('#timeline-generated-clips'); generated.replaceChildren();
      const blank = document.createElement('option'); blank.value = ''; blank.textContent = data.generated_job_ids.length ? 'Choose a generated clip' : 'No generated clips detected'; generated.append(blank);
      data.generated_job_ids.forEach(id => { const option = document.createElement('option'); option.value = id; option.textContent = id; generated.append(option); });
      await loadProjectList(); refreshExportButton();
    } catch (error) { timelineMessage(error.message, 'error'); exportState('UNAVAILABLE', error.message, 'unavailable'); }
  }

  document.querySelector('#timeline-upload-clips').addEventListener('click', addSelectedClips);
  document.querySelector('#timeline-import-generated').addEventListener('click', importGeneratedClip);
  document.querySelector('#timeline-play-sequence').addEventListener('click', () => playTimelineClip(0, true));
  document.querySelector('#timeline-save-project').addEventListener('click', () => saveProject().catch(error => timelineMessage(error.message, 'error')));
  document.querySelector('#timeline-open-project').addEventListener('click', loadProject);
  document.querySelector('#timeline-new-project').addEventListener('click', newProject);
  document.querySelector('#timeline-export').addEventListener('click', startExport);
  document.querySelector('#timeline-project-name').addEventListener('input', markDirty);
  document.querySelector('#timeline-profile').addEventListener('change', markDirty);
  document.querySelector('#timeline-voice-input').addEventListener('change', event => selectAudio(event, 'voice'));
  document.querySelector('#timeline-music-input').addEventListener('change', event => selectAudio(event, 'music'));
  ['voice', 'music'].forEach(kind => document.querySelector(`#timeline-${kind}-volume`).addEventListener('input', () => { markDirty(); renderAudioNames(); }));

  renderTimeline(); renderAudioNames(); loadCapabilities();
})();
