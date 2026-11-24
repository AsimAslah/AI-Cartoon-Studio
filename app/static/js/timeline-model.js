((root) => {
  const clone = value => typeof structuredClone === 'function'
    ? structuredClone(value)
    : JSON.parse(JSON.stringify(value));

  function clipDuration(clip) {
    if (clip.scene_type === 'video') {
      if (!clip.media) return 0;
      return Math.max(0, Number(clip.trim_end_seconds ?? clip.media.duration_seconds) - Number(clip.trim_start_seconds || 0));
    }
    return Math.max(0, Number(clip.duration_seconds || 0));
  }

  function computeLayout(clips) {
    let cursor = 0;
    return clips.map((clip, index) => {
      const duration = clipDuration(clip);
      const entry = {index, clip_id: clip.clip_id, start: cursor, end: cursor + duration, duration};
      cursor += duration;
      if (index < clips.length - 1 && clip.transition_to_next !== 'cut') {
        cursor -= Math.min(Number(clip.transition_duration_seconds || 0), duration);
      }
      return entry;
    });
  }

  function normalize(clips) {
    return clips.map((clip, order) => ({...clip, order}));
  }

  function reorder(clips, fromIndex, toIndex) {
    if (fromIndex < 0 || fromIndex >= clips.length || toIndex < 0 || toIndex >= clips.length || fromIndex === toIndex) {
      return normalize(clone(clips));
    }
    const result = clone(clips);
    const [moved] = result.splice(fromIndex, 1);
    result.splice(toIndex, 0, moved);
    return normalize(result);
  }

  function splitAt(clips, playhead, idFactory = () => crypto.randomUUID()) {
    const layout = computeLayout(clips);
    const entry = layout.find(item => playhead > item.start + 0.05 && playhead < item.end - 0.05);
    if (!entry) return null;
    const result = clone(clips);
    const first = result[entry.index];
    const second = clone(first);
    second.clip_id = idFactory();
    const firstDuration = playhead - entry.start;
    const originalTransition = first.transition_to_next;
    if (first.scene_type === 'video') {
      const splitSourceTime = Number(first.trim_start_seconds || 0) + firstDuration;
      second.trim_start_seconds = splitSourceTime;
      first.trim_end_seconds = splitSourceTime;
    } else {
      second.duration_seconds = entry.duration - firstDuration;
      first.duration_seconds = firstDuration;
    }
    first.transition_to_next = 'cut';
    second.transition_to_next = originalTransition;
    result.splice(entry.index + 1, 0, second);
    return normalize(result);
  }

  class History {
    constructor(limit = 50) { this.limit = limit; this.undoStack = []; this.redoStack = []; }
    record(snapshot) {
      this.undoStack.push(clone(snapshot));
      if (this.undoStack.length > this.limit) this.undoStack.shift();
      this.redoStack = [];
    }
    undo(current) {
      if (!this.undoStack.length) return null;
      this.redoStack.push(clone(current));
      return this.undoStack.pop();
    }
    redo(current) {
      if (!this.redoStack.length) return null;
      this.undoStack.push(clone(current));
      return this.redoStack.pop();
    }
    clear() { this.undoStack = []; this.redoStack = []; }
  }

  const api = {clipDuration, computeLayout, reorder, splitAt, History};
  root.TimelineModel = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
