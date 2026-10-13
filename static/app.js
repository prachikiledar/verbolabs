// Subtitle Studio - Modern Audio Waveform & Subtitle Engine
document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    videoLoaded: false,
    audioLoaded: false,
    videoFilename: null,
    audioFilename: null,
    videoDuration: 14.5, // Total duration in seconds
    projectId: null,
    subtitleId: null,
    cues: [],
    stats: {},
    warnings: [],
    activeCueId: null,
    zoomLevel: 1.0,
    audioCtx: null,
    audioBuffer: null,
    audioWaveData: null, // Array of amplitude peaks [0..1]
    isDraggingPlayhead: false
  };

  // DOM Elements
  const video = document.getElementById('main-video');
  const audio = document.getElementById('main-audio');
  const videoOverlay = document.getElementById('video-sub-overlay');
  const videoSubText = document.getElementById('video-sub-text');
  
  const videoDropZone = document.getElementById('video-drop-zone');
  const videoFileInput = document.getElementById('video-file-input');
  const videoProgress = document.getElementById('video-progress-overlay');
  const videoProgressText = document.getElementById('video-progress-text');
  const videoFileInfo = document.getElementById('video-file-info');
  const videoNameDisplay = document.getElementById('video-name-display');

  const subsDropZone = document.getElementById('subs-drop-zone');
  const subsFileInput = document.getElementById('subs-file-input');
  const subsFileInfo = document.getElementById('subs-file-info');
  const subsNameDisplay = document.getElementById('subs-name-display');
  const subsCueCountBadge = document.getElementById('subs-cue-count-badge');
  const rawSubTextarea = document.getElementById('raw-subs-textarea');
  const btnParseRaw = document.getElementById('btn-parse-raw');

  const tabBtnFile = document.getElementById('tab-btn-file');
  const tabBtnPaste = document.getElementById('tab-btn-paste');
  const subFileTab = document.getElementById('sub-file-tab');
  const subPasteTab = document.getElementById('sub-paste-tab');

  const videoStatusPill = document.getElementById('video-status-pill');
  const audioStatusPill = document.getElementById('audio-status-pill');
  const subsStatusPill = document.getElementById('subs-status-pill');

  const btnLoadSample = document.getElementById('btn-load-sample');
  const btnDownloadAudio = document.getElementById('btn-download-audio');

  // Video Playback Controls
  const btnVideoPlayToggle = document.getElementById('btn-video-play-toggle');
  const stagePlayIcon = document.getElementById('stage-play-icon');
  const stagePauseIcon = document.getElementById('stage-pause-icon');
  const currentTimeText = document.getElementById('current-time-text');
  const totalTimeText = document.getElementById('total-time-text');
  const speedButtons = document.querySelectorAll('.speed-btn');

  // Waveform Timeline Stage Elements
  const timelineViewport = document.getElementById('timeline-viewport');
  const timelineTrackWrapper = document.getElementById('timeline-track-wrapper');
  const timelineRuler = document.getElementById('timeline-ruler');
  const waveformStage = document.getElementById('waveform-stage');
  const waveformCanvas = document.getElementById('waveform-canvas');
  const subtitlesTrack = document.getElementById('subtitles-timeline-track');
  const timelinePlayhead = document.getElementById('timeline-playhead');
  const playheadTag = document.getElementById('playhead-tag');

  // Toolbar Actions
  const btnAddCue = document.getElementById('btn-add-cue');
  const btnSaveDb = document.getElementById('btn-save-db');
  const btnToggleShifter = document.getElementById('btn-toggle-shifter');
  const timeShiftBar = document.getElementById('time-shift-bar');
  const shiftButtons = document.querySelectorAll('.shift-btn');
  const customShiftInput = document.getElementById('custom-shift-value');
  const btnApplyCustomShift = document.getElementById('btn-apply-custom-shift');
  const btnZoomIn = document.getElementById('btn-zoom-in');
  const btnZoomOut = document.getElementById('btn-zoom-out');
  const zoomLevelText = document.getElementById('zoom-level-text');

  // Active Cue Inspector
  const activeCueInspector = document.getElementById('active-cue-inspector');
  const inspectorCueNum = document.getElementById('inspector-cue-num');
  const inspectorStartInput = document.getElementById('inspector-start-input');
  const inspectorEndInput = document.getElementById('inspector-end-input');
  const inspectorDurationTag = document.getElementById('inspector-duration-tag');
  const inspectorTextInput = document.getElementById('inspector-text-input');
  const btnInspectorPlay = document.getElementById('btn-inspector-play');
  const btnInspectorClip = document.getElementById('btn-inspector-clip');
  const btnInspectorDelete = document.getElementById('btn-inspector-delete');

  // Export
  const btnExportDropdown = document.getElementById('btn-export-dropdown');
  const exportMenu = document.getElementById('export-menu');

  // Diagnostics Metrics
  const statCues = document.getElementById('stat-cues');
  const statWords = document.getElementById('stat-words');
  const statCps = document.getElementById('stat-cps');
  const statCoverage = document.getElementById('stat-coverage');
  const warningsBox = document.getElementById('warnings-box');
  const warningsCountText = document.getElementById('warnings-count-text');

  // Collapsible sections
  const uploadSection = document.getElementById('upload-section');
  const activeMediaStrip = document.getElementById('active-media-strip');
  const btnToggleUpload = document.getElementById('btn-toggle-upload');
  const btnReopenImport = document.getElementById('btn-reopen-import');

  // -------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------
  function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3500);
  }

  function formatShortSec(sec) {
    if (isNaN(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ds = Math.floor((sec % 1) * 10);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ds}`;
  }

  function formatTimestamp(sec) {
    if (isNaN(sec) || sec < 0) sec = 0;
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec - Math.floor(sec)) * 1000);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
  }

  function parseFormattedTimestamp(ts) {
    if (!ts) return null;
    const clean = ts.trim().replace(',', '.');
    const parts = clean.split(':');
    if (parts.length === 3) {
      const h = parseFloat(parts[0]) || 0;
      const m = parseFloat(parts[1]) || 0;
      const s = parseFloat(parts[2]) || 0;
      return h * 3600 + m * 60 + s;
    } else if (parts.length === 2) {
      const m = parseFloat(parts[0]) || 0;
      const s = parseFloat(parts[1]) || 0;
      return m * 60 + s;
    } else if (!isNaN(clean)) {
      return parseFloat(clean);
    }
    return null;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function getTotalDuration() {
    let dur = state.videoDuration || 14.5;
    if (video.duration && !isNaN(video.duration) && video.duration > 0) {
      dur = Math.max(dur, video.duration);
    }
    if (state.cues.length > 0) {
      const lastCueEnd = state.cues[state.cues.length - 1].end;
      if (lastCueEnd + 1 > dur) dur = lastCueEnd + 1;
    }
    return Math.max(dur, 5);
  }

  function getTimelineWidth() {
    const baseWidth = Math.max(timelineViewport.clientWidth || 1000, 1000);
    return baseWidth * state.zoomLevel;
  }

  function updateActiveMediaBar() {
    if (state.videoLoaded || state.cues.length > 0) {
      if (activeMediaStrip) activeMediaStrip.style.display = 'flex';
      if (uploadSection) uploadSection.classList.add('collapsed');
      const toggleText = document.getElementById('upload-toggle-text');
      if (toggleText) toggleText.textContent = uploadSection && uploadSection.classList.contains('collapsed') ? 'Import Media' : 'Hide Import';
    }
  }

  // -------------------------------------------------------------
  // Waveform Drawing Engine
  // -------------------------------------------------------------
  function generateSyntheticWaveform(pointsCount = 600) {
    const data = [];
    for (let i = 0; i < pointsCount; i++) {
      // Natural speech cadence pattern (bursts of words + small silence gaps)
      const t = i / pointsCount;
      const speechCluster = Math.sin(t * 30) * Math.sin(t * 11);
      const isVoice = speechCluster > -0.2;
      if (isVoice) {
        const amp = 0.25 + Math.random() * 0.65;
        data.push(amp);
      } else {
        data.push(0.04 + Math.random() * 0.08); // Background silence
      }
    }
    return data;
  }

  function drawWaveform() {
    if (!waveformCanvas) return;
    const ctx = waveformCanvas.getContext('2d');
    const width = getTimelineWidth();
    const height = 128;

    waveformCanvas.width = width;
    waveformCanvas.height = height;

    ctx.clearRect(0, 0, width, height);

    // Audio Waveform Peaks Data
    const wave = state.audioWaveData || generateSyntheticWaveform(Math.floor(width / 3));
    const step = width / wave.length;
    const centerY = height / 2;

    // Gradient styling for speech peaks
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, 'rgba(56, 189, 248, 0.85)');   // Cyan top
    grad.addColorStop(0.5, 'rgba(129, 140, 248, 0.95)'); // Indigo center
    grad.addColorStop(1, 'rgba(192, 132, 252, 0.85)');  // Purple bottom

    ctx.fillStyle = grad;

    for (let i = 0; i < wave.length; i++) {
      const amp = wave[i] || 0.05;
      const barHeight = Math.max(3, amp * (height * 0.78));
      const x = i * step;
      const y = centerY - barHeight / 2;
      const barWidth = Math.max(1.5, step - 1);

      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, y, barWidth, barHeight, 1.5) : ctx.rect(x, y, barWidth, barHeight);
      ctx.fill();
    }

    // Center subtle guide line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.stroke();
  }

  async function decodeAudioFromUrl(url) {
    try {
      if (!state.audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        state.audioCtx = new AudioContext();
      }
      const response = await fetch(url);
      const arrayBuffer = await response.arrayBuffer();
      const decoded = await state.audioCtx.decodeAudioData(arrayBuffer);
      state.audioBuffer = decoded;

      // Extract RMS peaks
      const channelData = decoded.getChannelData(0);
      const samples = 800;
      const blockSize = Math.floor(channelData.length / samples);
      const peaks = [];
      for (let i = 0; i < samples; i++) {
        let max = 0;
        for (let j = 0; j < blockSize; j++) {
          const val = Math.abs(channelData[i * blockSize + j]);
          if (val > max) max = val;
        }
        peaks.push(max);
      }
      state.audioWaveData = peaks;
      drawWaveform();
    } catch (e) {
      console.warn('Audio decoding fallback to procedural wave:', e);
      state.audioWaveData = generateSyntheticWaveform();
      drawWaveform();
    }
  }

  // -------------------------------------------------------------
  // Timeline Subtitle Rendering Engine
  // -------------------------------------------------------------
  function renderTimeline() {
    const totalDuration = getTotalDuration();
    const trackWidth = getTimelineWidth();

    timelineTrackWrapper.style.width = `${trackWidth}px`;

    // Render Ruler Ticks
    timelineRuler.innerHTML = '';
    const tickInterval = totalDuration > 60 ? 5 : (totalDuration > 30 ? 2 : 1);
    for (let s = 0; s <= totalDuration; s += tickInterval) {
      const tickLeft = (s / totalDuration) * trackWidth;
      const tick = document.createElement('div');
      tick.className = 'ruler-tick';
      tick.style.left = `${tickLeft}px`;
      tick.textContent = formatShortSec(s);
      timelineRuler.appendChild(tick);
    }

    // Redraw Waveform Canvas
    drawWaveform();

    // Render Subtitle Blocks Directly on the Waveform
    subtitlesTrack.innerHTML = '';

    state.cues.forEach((cue) => {
      const leftPx = (cue.start / totalDuration) * trackWidth;
      const widthPx = Math.max(34, (cue.duration / totalDuration) * trackWidth);

      const block = document.createElement('div');
      block.className = `timeline-cue-block ${state.activeCueId === cue.id ? 'active' : ''}`;
      block.dataset.cueId = cue.id;
      block.style.left = `${leftPx}px`;
      block.style.width = `${widthPx}px`;

      block.innerHTML = `
        <div class="cue-handle cue-handle-left" title="Drag to adjust start time"></div>
        <div class="cue-block-header">
          <span class="cue-block-badge">#${cue.id}</span>
          <span class="cue-block-time">${formatShortSec(cue.start)} - ${formatShortSec(cue.end)}</span>
          <button class="cue-block-del" title="Delete subtitle">&times;</button>
        </div>
        <input type="text" class="cue-block-inline-input" value="${escapeHtml(cue.text || '')}" placeholder="Type subtitle here..." spellcheck="false">
        <div class="cue-handle cue-handle-right" title="Drag to adjust end time"></div>
      `;

      // 1. Click block -> select & seek
      block.addEventListener('click', (e) => {
        if (e.target.classList.contains('cue-block-del')) return;
        selectCue(cue.id);
        seekToTime(cue.start);
      });

      // 2. Typing inside block on the wave -> immediate live update!
      const inlineInput = block.querySelector('.cue-block-inline-input');
      inlineInput.addEventListener('input', (e) => {
        cue.text = e.target.value;
        if (state.activeCueId === cue.id && inspectorTextInput) {
          inspectorTextInput.value = cue.text;
        }
        updateVideoSubtitleOverlay(video.currentTime || 0);
        recalcStatsLocally();
      });

      inlineInput.addEventListener('focus', () => {
        selectCue(cue.id);
      });

      // 3. Delete subtitle cue
      const delBtn = block.querySelector('.cue-block-del');
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteCue(cue.id);
      });

      // 4. Drag Left Handle (Start Time resize)
      const leftHandle = block.querySelector('.cue-handle-left');
      leftHandle.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        e.preventDefault();
        startDragResize(e, cue, 'start');
      });

      // 5. Drag Right Handle (End Time resize)
      const rightHandle = block.querySelector('.cue-handle-right');
      rightHandle.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        e.preventDefault();
        startDragResize(e, cue, 'end');
      });

      // 6. Drag whole block along the wavelength
      block.addEventListener('mousedown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.closest('.cue-handle') || e.target.closest('.cue-block-del')) {
          return;
        }
        e.preventDefault();
        startDragMove(e, cue);
      });

      subtitlesTrack.appendChild(block);
    });

    // Update Diagnostics
    recalcStatsLocally();
    updatePlayheadPosition();
  }

  // -------------------------------------------------------------
  // Drag Move & Resize Handlers on Timeline
  // -------------------------------------------------------------
  function startDragResize(e, cue, handleType) {
    selectCue(cue.id);
    const totalDuration = getTotalDuration();
    const trackWidth = getTimelineWidth();
    const startX = e.clientX;
    const initialStart = cue.start;
    const initialEnd = cue.end;

    function onMouseMove(moveEvent) {
      const deltaX = moveEvent.clientX - startX;
      const deltaTime = (deltaX / trackWidth) * totalDuration;

      if (handleType === 'start') {
        let newStart = parseFloat(Math.max(0, Math.min(initialEnd - 0.2, initialStart + deltaTime)).toFixed(3));
        cue.start = newStart;
        cue.duration = parseFloat((cue.end - cue.start).toFixed(3));
        cue.start_formatted = formatTimestamp(cue.start);
      } else {
        let newEnd = parseFloat(Math.min(totalDuration, Math.max(initialStart + 0.2, initialEnd + deltaTime)).toFixed(3));
        cue.end = newEnd;
        cue.duration = parseFloat((cue.end - cue.start).toFixed(3));
        cue.end_formatted = formatTimestamp(cue.end);
      }

      updateCueDOM(cue);
      updateInspector(cue);
      updateVideoSubtitleOverlay(video.currentTime || 0);
    }

    function onMouseUp() {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      state.cues.sort((a, b) => a.start - b.start);
      state.cues.forEach((c, i) => c.id = i + 1);
      renderTimeline();
      selectCue(cue.id);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  function startDragMove(e, cue) {
    selectCue(cue.id);
    const totalDuration = getTotalDuration();
    const trackWidth = getTimelineWidth();
    const startX = e.clientX;
    const initialStart = cue.start;
    const duration = cue.duration;

    const block = document.querySelector(`.timeline-cue-block[data-cue-id="${cue.id}"]`);
    if (block) block.classList.add('dragging');

    function onMouseMove(moveEvent) {
      const deltaX = moveEvent.clientX - startX;
      const deltaTime = (deltaX / trackWidth) * totalDuration;

      let newStart = parseFloat(Math.max(0, Math.min(totalDuration - duration, initialStart + deltaTime)).toFixed(3));
      let newEnd = parseFloat((newStart + duration).toFixed(3));

      cue.start = newStart;
      cue.end = newEnd;
      cue.start_formatted = formatTimestamp(cue.start);
      cue.end_formatted = formatTimestamp(cue.end);

      updateCueDOM(cue);
      updateInspector(cue);
      seekToTime(cue.start);
    }

    function onMouseUp() {
      if (block) block.classList.remove('dragging');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      state.cues.sort((a, b) => a.start - b.start);
      state.cues.forEach((c, i) => c.id = i + 1);
      renderTimeline();
      selectCue(cue.id);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  function updateCueDOM(cue) {
    const totalDuration = getTotalDuration();
    const trackWidth = getTimelineWidth();
    const block = document.querySelector(`.timeline-cue-block[data-cue-id="${cue.id}"]`);
    if (!block) return;

    const leftPx = (cue.start / totalDuration) * trackWidth;
    const widthPx = Math.max(34, (cue.duration / totalDuration) * trackWidth);

    block.style.left = `${leftPx}px`;
    block.style.width = `${widthPx}px`;

    const timeTag = block.querySelector('.cue-block-time');
    if (timeTag) timeTag.textContent = `${formatShortSec(cue.start)} - ${formatShortSec(cue.end)}`;
  }

  // -------------------------------------------------------------
  // Double-Click on Waveform -> Add Subtitle directly on Audio Wave
  // -------------------------------------------------------------
  waveformStage.addEventListener('dblclick', (e) => {
    // If clicked directly on an input or delete button, ignore
    if (e.target.tagName === 'INPUT' || e.target.closest('.cue-block-del')) return;

    const rect = timelineTrackWrapper.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const trackWidth = getTimelineWidth();
    const totalDuration = getTotalDuration();

    let clickTime = (clickX / trackWidth) * totalDuration;
    if (clickTime < 0) clickTime = 0;
    if (clickTime > totalDuration) clickTime = totalDuration;

    const duration = 2.5;
    const newCue = {
      id: state.cues.length + 1,
      start: parseFloat(clickTime.toFixed(3)),
      end: parseFloat(Math.min(totalDuration, clickTime + duration).toFixed(3)),
      duration: duration,
      text: '', // Empty dialogue so user types their own cleanly
      start_formatted: formatTimestamp(clickTime),
      end_formatted: formatTimestamp(Math.min(totalDuration, clickTime + duration)),
      char_count: 0,
      word_count: 0,
      cps: 0.0
    };

    state.cues.push(newCue);
    state.cues.sort((a, b) => a.start - b.start);
    state.cues.forEach((c, i) => c.id = i + 1);

    renderTimeline();
    selectCue(newCue.id);
    seekToTime(newCue.start);
    updateActiveMediaBar();

    // Auto focus the inline input on the newly placed wave subtitle
    setTimeout(() => {
      const newBlock = document.querySelector(`.timeline-cue-block[data-cue-id="${newCue.id}"]`);
      if (newBlock) {
        const input = newBlock.querySelector('.cue-block-inline-input');
        if (input) {
          input.focus();
          input.select();
        }
      }
    }, 50);

    showToast(`Subtitle inserted on wavelength at ${formatShortSec(clickTime)}`);
  });

  // Single Click on Waveform -> Seek playhead
  waveformStage.addEventListener('click', (e) => {
    if (e.target.closest('.timeline-cue-block')) return; // handled by block
    const rect = timelineTrackWrapper.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const trackWidth = getTimelineWidth();
    const totalDuration = getTotalDuration();
    const seekTime = Math.max(0, Math.min(totalDuration, (clickX / trackWidth) * totalDuration));
    seekToTime(seekTime);
  });

  // -------------------------------------------------------------
  // Add Cue Button at Current Playhead
  // -------------------------------------------------------------
  if (btnAddCue) {
    btnAddCue.addEventListener('click', () => {
      const currentTime = video.currentTime || 0;
      const totalDuration = getTotalDuration();
      const duration = 2.5;

      const newCue = {
        id: state.cues.length + 1,
        start: parseFloat(currentTime.toFixed(3)),
        end: parseFloat(Math.min(totalDuration, currentTime + duration).toFixed(3)),
        duration: duration,
        text: '', // Empty, no unwanted default text
        start_formatted: formatTimestamp(currentTime),
        end_formatted: formatTimestamp(Math.min(totalDuration, currentTime + duration)),
        char_count: 0,
        word_count: 0,
        cps: 0.0
      };

      state.cues.push(newCue);
      state.cues.sort((a, b) => a.start - b.start);
      state.cues.forEach((c, i) => c.id = i + 1);

      renderTimeline();
      selectCue(newCue.id);
      updateActiveMediaBar();

      setTimeout(() => {
        const newBlock = document.querySelector(`.timeline-cue-block[data-cue-id="${newCue.id}"]`);
        if (newBlock) {
          const input = newBlock.querySelector('.cue-block-inline-input');
          if (input) input.focus();
        }
      }, 50);

      showToast(`Subtitle added on wave at ${formatShortSec(currentTime)}`);
    });
  }

  // -------------------------------------------------------------
  // Cue Selection & Live Inspector
  // -------------------------------------------------------------
  function selectCue(cueId) {
    state.activeCueId = cueId;
    const cue = state.cues.find(c => c.id === cueId);

    // Update active highlight on timeline blocks
    document.querySelectorAll('.timeline-cue-block').forEach(b => {
      b.classList.toggle('active', parseInt(b.dataset.cueId, 10) === cueId);
    });

    if (cue) {
      updateInspector(cue);
    } else {
      if (activeCueInspector) activeCueInspector.style.display = 'none';
    }
  }

  function updateInspector(cue) {
    if (!activeCueInspector) return;
    activeCueInspector.style.display = 'flex';

    if (inspectorCueNum) inspectorCueNum.textContent = `#${cue.id}`;
    if (inspectorStartInput) inspectorStartInput.value = formatTimestamp(cue.start);
    if (inspectorEndInput) inspectorEndInput.value = formatTimestamp(cue.end);
    if (inspectorDurationTag) inspectorDurationTag.textContent = `${cue.duration.toFixed(1)}s`;
    if (inspectorTextInput) inspectorTextInput.value = cue.text || '';
  }

  if (inspectorTextInput) {
    inspectorTextInput.addEventListener('input', (e) => {
      const cue = state.cues.find(c => c.id === state.activeCueId);
      if (!cue) return;
      cue.text = e.target.value;

      // Update block on timeline
      const block = document.querySelector(`.timeline-cue-block[data-cue-id="${cue.id}"]`);
      if (block) {
        const input = block.querySelector('.cue-block-inline-input');
        if (input && input.value !== cue.text) input.value = cue.text;
      }
      updateVideoSubtitleOverlay(video.currentTime || 0);
      recalcStatsLocally();
    });
  }

  if (inspectorStartInput) {
    inspectorStartInput.addEventListener('change', (e) => {
      const cue = state.cues.find(c => c.id === state.activeCueId);
      if (!cue) return;
      const parsed = parseFormattedTimestamp(e.target.value);
      if (parsed !== null && parsed < cue.end) {
        cue.start = parseFloat(parsed.toFixed(3));
        cue.duration = parseFloat((cue.end - cue.start).toFixed(3));
        cue.start_formatted = formatTimestamp(cue.start);
        renderTimeline();
        selectCue(cue.id);
      } else {
        e.target.value = formatTimestamp(cue.start);
      }
    });
  }

  if (inspectorEndInput) {
    inspectorEndInput.addEventListener('change', (e) => {
      const cue = state.cues.find(c => c.id === state.activeCueId);
      if (!cue) return;
      const parsed = parseFormattedTimestamp(e.target.value);
      if (parsed !== null && parsed > cue.start) {
        cue.end = parseFloat(parsed.toFixed(3));
        cue.duration = parseFloat((cue.end - cue.start).toFixed(3));
        cue.end_formatted = formatTimestamp(cue.end);
        renderTimeline();
        selectCue(cue.id);
      } else {
        e.target.value = formatTimestamp(cue.end);
      }
    });
  }

  if (btnInspectorPlay) {
    btnInspectorPlay.addEventListener('click', () => {
      const cue = state.cues.find(c => c.id === state.activeCueId);
      if (!cue) return;
      seekToTime(cue.start);
      video.play();
      audio.play().catch(() => {});

      const stopCheck = () => {
        if (video.currentTime >= cue.end) {
          video.pause();
          audio.pause();
          video.removeEventListener('timeupdate', stopCheck);
        }
      };
      video.addEventListener('timeupdate', stopCheck);
    });
  }

  if (btnInspectorClip) {
    btnInspectorClip.addEventListener('click', async () => {
      const cue = state.cues.find(c => c.id === state.activeCueId);
      if (!cue) return;
      showToast(`Generating MP3 clip for cue #${cue.id}...`, 'success');
      try {
        const response = await fetch('/api/clip-audio', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            start: cue.start,
            end: cue.end,
            audio_filename: state.audioFilename || 'sample_extracted.mp3'
          })
        });
        if (response.ok) {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `clip_cue_${cue.id}.mp3`;
          a.click();
          showToast('Audio clip downloaded!');
        } else {
          showToast('Failed to clip audio', 'error');
        }
      } catch (err) {
        showToast('Error clipping audio: ' + err.message, 'error');
      }
    });
  }

  if (btnInspectorDelete) {
    btnInspectorDelete.addEventListener('click', () => {
      if (state.activeCueId) {
        deleteCue(state.activeCueId);
      }
    });
  }

  function deleteCue(cueId) {
    state.cues = state.cues.filter(c => c.id !== cueId);
    state.cues.forEach((c, i) => c.id = i + 1);
    if (state.activeCueId === cueId) {
      state.activeCueId = null;
      if (activeCueInspector) activeCueInspector.style.display = 'none';
    }
    renderTimeline();
    updateActiveMediaBar();
    showToast('Subtitle cue deleted');
  }

  // -------------------------------------------------------------
  // Video Playback & Playhead Tracking
  // -------------------------------------------------------------
  function seekToTime(timeSec) {
    if (video) video.currentTime = timeSec;
    if (audio) audio.currentTime = timeSec;
    updatePlayheadPosition();
    updateVideoSubtitleOverlay(timeSec);
  }

  function updatePlayheadPosition() {
    if (!timelinePlayhead) return;
    const totalDuration = getTotalDuration();
    const trackWidth = getTimelineWidth();
    const curr = video.currentTime || 0;

    const playheadPx = (curr / totalDuration) * trackWidth;
    timelinePlayhead.style.left = `${playheadPx}px`;

    if (playheadTag) {
      playheadTag.textContent = formatShortSec(curr);
    }
    if (currentTimeText) {
      currentTimeText.textContent = formatShortSec(curr);
    }
    if (totalTimeText) {
      totalTimeText.textContent = formatShortSec(totalDuration);
    }
  }

  function updateVideoSubtitleOverlay(currTime) {
    if (!videoOverlay || !videoSubText) return;
    const activeCue = state.cues.find(c => currTime >= c.start && currTime <= c.end);

    if (activeCue && activeCue.text && activeCue.text.trim()) {
      videoSubText.textContent = activeCue.text;
      videoOverlay.style.display = 'flex';
      
      // Auto highlight active cue block on timeline
      document.querySelectorAll('.timeline-cue-block').forEach(b => {
        b.classList.toggle('active', parseInt(b.dataset.cueId, 10) === activeCue.id);
      });
    } else {
      videoOverlay.style.display = 'none';
    }
  }

  if (video) {
    video.addEventListener('timeupdate', () => {
      updatePlayheadPosition();
      updateVideoSubtitleOverlay(video.currentTime);
    });

    video.addEventListener('loadedmetadata', () => {
      state.videoDuration = video.duration || 14.5;
      renderTimeline();
    });

    video.addEventListener('play', () => {
      if (stagePlayIcon) stagePlayIcon.style.display = 'none';
      if (stagePauseIcon) stagePauseIcon.style.display = 'block';
      if (audio && audio.paused) audio.play().catch(() => {});
    });

    video.addEventListener('pause', () => {
      if (stagePlayIcon) stagePlayIcon.style.display = 'block';
      if (stagePauseIcon) stagePauseIcon.style.display = 'none';
      if (audio && !audio.paused) audio.pause();
    });
  }

  if (btnVideoPlayToggle) {
    btnVideoPlayToggle.addEventListener('click', togglePlay);
  }

  function togglePlay() {
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
      if (audio) audio.play().catch(() => {});
    } else {
      video.pause();
      if (audio) audio.pause();
    }
  }

  // Keyboard shortcut: Spacebar toggles video
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      togglePlay();
    }
  });

  // Playback Speed Controls
  speedButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      speedButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const speed = parseFloat(btn.dataset.speed);
      if (video) video.playbackRate = speed;
      if (audio) audio.playbackRate = speed;
    });
  });

  // Timeline Zoom Controls
  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      if (state.zoomLevel < 3.0) {
        state.zoomLevel = parseFloat((state.zoomLevel + 0.5).toFixed(1));
        if (zoomLevelText) zoomLevelText.textContent = `${state.zoomLevel}x`;
        renderTimeline();
      }
    });
  }

  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      if (state.zoomLevel > 1.0) {
        state.zoomLevel = parseFloat((state.zoomLevel - 0.5).toFixed(1));
        if (zoomLevelText) zoomLevelText.textContent = `${state.zoomLevel}x`;
        renderTimeline();
      }
    });
  }

  // -------------------------------------------------------------
  // Shift Subtitles Time Bar
  // -------------------------------------------------------------
  if (btnToggleShifter) {
    btnToggleShifter.addEventListener('click', () => {
      if (timeShiftBar) timeShiftBar.classList.toggle('show');
    });
  }

  function shiftAllCues(deltaSec) {
    if (!state.cues.length) return;
    state.cues.forEach(cue => {
      cue.start = parseFloat(Math.max(0, cue.start + deltaSec).toFixed(3));
      cue.end = parseFloat(Math.max(cue.start + 0.2, cue.end + deltaSec).toFixed(3));
      cue.start_formatted = formatTimestamp(cue.start);
      cue.end_formatted = formatTimestamp(cue.end);
    });
    renderTimeline();
    if (state.activeCueId) selectCue(state.activeCueId);
    showToast(`Shifted all subtitles by ${deltaSec > 0 ? '+' : ''}${deltaSec}s`);
  }

  shiftButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const shift = parseFloat(btn.dataset.shift);
      shiftAllCues(shift);
    });
  });

  if (btnApplyCustomShift && customShiftInput) {
    btnApplyCustomShift.addEventListener('click', () => {
      const val = parseFloat(customShiftInput.value);
      if (!isNaN(val)) {
        shiftAllCues(val);
      }
    });
  }

  // -------------------------------------------------------------
  // Recalculate Subtitle Diagnostics & Metrics
  // -------------------------------------------------------------
  function recalcStatsLocally() {
    let totalWords = 0;
    let totalChars = 0;
    let totalDur = 0;

    state.cues.forEach(c => {
      const txt = (c.text || '').trim();
      const words = txt ? txt.split(/\s+/).length : 0;
      const chars = txt.length;
      c.word_count = words;
      c.char_count = chars;
      c.cps = c.duration > 0 ? parseFloat((chars / c.duration).toFixed(1)) : 0;

      totalWords += words;
      totalChars += chars;
      totalDur += c.duration;
    });

    const avgCps = totalDur > 0 ? (totalChars / totalDur).toFixed(1) : '0.0';
    const coverage = getTotalDuration() > 0 ? Math.min(100, Math.round((totalDur / getTotalDuration()) * 100)) : 0;

    if (statCues) statCues.textContent = state.cues.length;
    if (statWords) statWords.textContent = totalWords;
    if (statCps) statCps.textContent = avgCps;
    if (statCoverage) statCoverage.textContent = `${coverage}%`;
    if (subsCueCountBadge) subsCueCountBadge.textContent = `${state.cues.length} Cues`;
  }

  // -------------------------------------------------------------
  // Database Save & File Export
  // -------------------------------------------------------------
  if (btnSaveDb) {
    btnSaveDb.addEventListener('click', async () => {
      try {
        const payload = {
          project_id: state.projectId,
          subtitle_id: state.subtitleId,
          video_duration: state.videoDuration || (video ? video.duration : 0.0),
          video_filename: state.videoFilename,
          audio_filename: state.audioFilename,
          cues: state.cues.map(c => {
            const start = parseFloat(c.start) || 0.0;
            const end = parseFloat(c.end) || 0.0;
            const dur = parseFloat(c.duration) || Math.max(0.1, +(end - start).toFixed(2));
            const txt = (c.text || '').toString();
            const charCount = c.char_count != null ? c.char_count : txt.length;
            const wordCount = c.word_count != null ? c.word_count : (txt.trim() ? txt.trim().split(/\s+/).length : 0);
            const cps = c.cps != null ? c.cps : (dur > 0 ? +(charCount / dur).toFixed(1) : 0.0);
            return {
              id: c.id,
              start: start,
              end: end,
              duration: dur,
              text: txt,
              char_count: charCount,
              word_count: wordCount,
              cps: cps
            };
          })
        };

        const response = await fetch('/api/subtitles/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (response.ok) {
          const res = await response.json();
          state.projectId = res.project_id;
          state.subtitleId = res.subtitle_id;
          showToast(`Saved ${res.cue_count || state.cues.length} subtitles to SQLite DB!`);
        } else {
          showToast('Failed to save to database', 'error');
        }
      } catch (err) {
        showToast('Error saving to DB: ' + err.message, 'error');
      }
    });
  }

  if (btnExportDropdown && exportMenu) {
    btnExportDropdown.addEventListener('click', (e) => {
      e.stopPropagation();
      exportMenu.classList.toggle('show');
    });

    document.addEventListener('click', () => {
      exportMenu.classList.remove('show');
    });

    exportMenu.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const fmt = item.dataset.format;
        exportSubtitles(fmt);
        exportMenu.classList.remove('show');
      });
    });
  }

  function exportSubtitles(format) {
    if (!state.cues.length) {
      showToast('No subtitles to export', 'error');
      return;
    }

    if (format === 'srt') {
      let srt = '';
      state.cues.forEach((c, idx) => {
        srt += `${idx + 1}\n${formatTimestamp(c.start)} --> ${formatTimestamp(c.end)}\n${c.text || ''}\n\n`;
      });
      downloadBlob(srt, 'subtitles.srt', 'text/plain');
    } else if (format === 'vtt') {
      let vtt = 'WEBVTT\n\n';
      state.cues.forEach((c, idx) => {
        const s = formatTimestamp(c.start).replace(',', '.');
        const e = formatTimestamp(c.end).replace(',', '.');
        vtt += `${idx + 1}\n${s} --> ${e}\n${c.text || ''}\n\n`;
      });
      downloadBlob(vtt, 'subtitles.vtt', 'text/vtt');
    } else if (format === 'txt') {
      const txt = state.cues.map(c => c.text || '').join('\n');
      downloadBlob(txt, 'subtitles.txt', 'text/plain');
    } else if (format === 'json') {
      const json = JSON.stringify(state.cues, null, 2);
      downloadBlob(json, 'subtitles.json', 'application/json');
    }
    showToast(`Exported ${format.toUpperCase()} successfully!`);
  }

  function downloadBlob(content, filename, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // -------------------------------------------------------------
  // Load Sample Demo Video & Waveform Subtitles
  // -------------------------------------------------------------
  if (btnLoadSample) {
    btnLoadSample.addEventListener('click', loadSampleWorkspace);
  }

  async function loadSampleWorkspace() {
    showToast('Loading demo media & waveform subtitles...');
    try {
      // First try /api/load-sample
      let data = null;
      let res = await fetch('/api/load-sample');
      if (res.ok) {
        data = await res.json();
      } else {
        res = await fetch('/api/sample/subtitles');
        if (res.ok) data = await res.json();
      }

      if (!data) throw new Error('Could not load demo sample');

      state.videoLoaded = true;
      state.audioLoaded = true;
      state.videoFilename = data.video_filename || 'demo_sample.mp4';
      state.audioFilename = data.audio_filename || 'demo_sample_extracted.mp3';
      state.videoDuration = data.duration || 8.0;
      state.projectId = data.project_id || 1;
      state.subtitleId = data.subtitle_id || 1;

      const vidUrl = data.video_url || '/media/demo_sample.mp4';
      const audUrl = data.audio_url || '/media/demo_sample_extracted.mp3';

      // 1. Set Video
      video.src = vidUrl;
      video.load();
      if (videoStatusPill) {
        videoStatusPill.className = 'pill pill-active';
        videoStatusPill.textContent = '🎬 Video: Loaded';
      }
      if (videoNameDisplay) videoNameDisplay.textContent = state.videoFilename;

      // 2. Set Audio
      audio.src = audUrl;
      audio.load();
      if (audioStatusPill) {
        audioStatusPill.className = 'pill pill-active';
        audioStatusPill.textContent = '🎵 Audio: Active';
      }
      if (btnDownloadAudio) {
        btnDownloadAudio.href = audUrl;
        btnDownloadAudio.style.display = 'inline-flex';
      }

      // Decode audio for waveform
      decodeAudioFromUrl(audUrl);

      // 3. Set Synced Subtitles
      state.cues = (data.cues || []).map((c, i) => ({
        id: i + 1,
        start: c.start,
        end: c.end,
        duration: parseFloat((c.end - c.start).toFixed(3)),
        text: c.text,
        start_formatted: formatTimestamp(c.start),
        end_formatted: formatTimestamp(c.end)
      }));

      if (subsStatusPill) {
        subsStatusPill.className = 'pill pill-active';
        subsStatusPill.textContent = `📝 Subs: ${state.cues.length} Cues`;
      }
      if (subsNameDisplay) subsNameDisplay.textContent = 'Waveform Synced Track';
      renderTimeline();
      if (state.cues.length > 0) selectCue(1);

      updateActiveMediaBar();
      showToast('Demo workspace ready! Edit directly on the audio waveform.');
    } catch (err) {
      showToast('Error loading sample: ' + err.message, 'error');
    }
  }

  // -------------------------------------------------------------
  // Video & Subtitle File Upload Handlers
  // -------------------------------------------------------------
  if (videoFileInput) {
    videoFileInput.addEventListener('change', handleVideoUpload);
  }

  async function handleVideoUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    if (videoProgress) videoProgress.style.display = 'flex';
    if (videoProgressText) videoProgressText.textContent = 'Uploading & extracting audio waveform...';

    const formData = new FormData();
    formData.append('file', file);

    try {
      let response = await fetch('/api/upload-video', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) response = await fetch('/api/extract-audio', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        state.videoLoaded = true;
        state.audioLoaded = true;
        state.videoFilename = data.video_filename;
        state.audioFilename = data.audio_filename;
        state.videoDuration = data.duration_seconds || 15;
        state.projectId = data.project_id;

        const videoBlobUrl = URL.createObjectURL(file);
        video.src = videoBlobUrl;
        video.load();

        if (data.audio_url) {
          audio.src = data.audio_url;
          audio.load();
          decodeAudioFromUrl(data.audio_url);
        }

        if (videoStatusPill) {
          videoStatusPill.className = 'pill pill-active';
          videoStatusPill.textContent = `🎬 Video: ${file.name}`;
        }
        if (audioStatusPill) {
          audioStatusPill.className = 'pill pill-active';
          audioStatusPill.textContent = '🎵 Audio: Extracted';
        }
        if (videoNameDisplay) videoNameDisplay.textContent = file.name;

        renderTimeline();
        updateActiveMediaBar();
        showToast('Video & audio waveform ready!');
      } else {
        showToast('Failed to extract audio from video', 'error');
      }
    } catch (err) {
      showToast('Error uploading video: ' + err.message, 'error');
    } finally {
      if (videoProgress) videoProgress.style.display = 'none';
    }
  }

  if (subsFileInput) {
    subsFileInput.addEventListener('change', handleSubsUpload);
  }

  async function handleSubsUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    if (state.projectId) formData.append('project_id', state.projectId);

    try {
      const response = await fetch('/api/subtitles/upload', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        loadParsedCues(data);
        if (subsNameDisplay) subsNameDisplay.textContent = file.name;
        showToast(`Loaded ${state.cues.length} subtitles onto waveform!`);
      } else {
        showToast('Failed to parse subtitle file', 'error');
      }
    } catch (err) {
      showToast('Error uploading subtitles: ' + err.message, 'error');
    }
  }

  if (btnParseRaw && rawSubTextarea) {
    btnParseRaw.addEventListener('click', async () => {
      const text = rawSubTextarea.value.trim();
      if (!text) return;
      try {
        const response = await fetch('/api/subtitles/parse-raw', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            raw_text: text,
            format: 'auto',
            project_id: state.projectId
          })
        });

        if (response.ok) {
          const data = await response.json();
          loadParsedCues(data);
          showToast(`Parsed ${state.cues.length} subtitles onto waveform!`);
        } else {
          showToast('Failed to parse subtitles', 'error');
        }
      } catch (err) {
        showToast('Error parsing raw text: ' + err.message, 'error');
      }
    });
  }

  function loadParsedCues(data) {
    state.cues = (data.cues || []).map((c, i) => ({
      id: i + 1,
      start: c.start,
      end: c.end,
      duration: parseFloat((c.end - c.start).toFixed(3)),
      text: c.text,
      start_formatted: formatTimestamp(c.start),
      end_formatted: formatTimestamp(c.end)
    }));
    if (data.project_id) state.projectId = data.project_id;
    if (subsStatusPill) {
      subsStatusPill.className = 'pill pill-active';
      subsStatusPill.textContent = `📝 Subs: ${state.cues.length} Cues`;
    }
    renderTimeline();
    if (state.cues.length > 0) selectCue(1);
    updateActiveMediaBar();
  }

  // Subtitle Tab Toggle
  if (tabBtnFile && tabBtnPaste && subFileTab && subPasteTab) {
    tabBtnFile.addEventListener('click', () => {
      tabBtnFile.classList.add('active');
      tabBtnPaste.classList.remove('active');
      subFileTab.style.display = 'block';
      subPasteTab.style.display = 'none';
    });

    tabBtnPaste.addEventListener('click', () => {
      tabBtnPaste.classList.add('active');
      tabBtnFile.classList.remove('active');
      subFileTab.style.display = 'none';
      subPasteTab.style.display = 'block';
    });
  }

  // Toggle Import Section
  if (btnToggleUpload) {
    btnToggleUpload.addEventListener('click', () => {
      if (uploadSection) {
        uploadSection.classList.toggle('collapsed');
        const toggleText = document.getElementById('upload-toggle-text');
        if (toggleText) toggleText.textContent = uploadSection.classList.contains('collapsed') ? 'Import Media' : 'Hide Import';
      }
    });
  }

  if (btnReopenImport) {
    btnReopenImport.addEventListener('click', () => {
      if (uploadSection) {
        uploadSection.classList.remove('collapsed');
        uploadSection.scrollIntoView({ behavior: 'smooth' });
        const toggleText = document.getElementById('upload-toggle-text');
        if (toggleText) toggleText.textContent = 'Hide Import';
      }
    });
  }

  // Handle Window Resize to keep Waveform perfectly scaled
  window.addEventListener('resize', () => {
    renderTimeline();
  });

  // Initial Boot Render & Auto-Load Demo Workspace
  renderTimeline();
  loadSampleWorkspace();
});
