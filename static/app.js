// Subtitle Studio - Frontend Engine
document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    videoLoaded: false,
    audioLoaded: false,
    videoFilename: null,
    audioFilename: null,
    videoDuration: 0,
    projectId: null,
    subtitleId: null,
    cues: [],
    stats: {},
    warnings: [],
    activeCueId: null,
    searchQuery: '',
    audioCtx: null,
    analyser: null,
    audioSource: null
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

  const waveformCanvas = document.getElementById('waveform-canvas');
  const canvasCtx = waveformCanvas.getContext('2d');
  const btnAudioPlay = document.getElementById('btn-audio-play');
  const audioPlayIcon = document.getElementById('audio-play-icon');
  const audioPauseIcon = document.getElementById('audio-pause-icon');
  const audioTimeDisplay = document.getElementById('audio-time-display');
  const audioScrubber = document.getElementById('audio-scrubber');

  const cuelistContainer = document.getElementById('cuelist-container');
  const emptyCuesState = document.getElementById('empty-cues-state');
  const subtitleSearch = document.getElementById('subtitle-search');
  const searchMatchesBadge = document.getElementById('search-matches-badge');
  const btnAddCue = document.getElementById('btn-add-cue');
  const btnSaveDb = document.getElementById('btn-save-db');

  const btnExportDropdown = document.getElementById('btn-export-dropdown');
  const exportMenu = document.getElementById('export-menu');

  const statCues = document.getElementById('stat-cues');
  const statWords = document.getElementById('stat-words');
  const statCps = document.getElementById('stat-cps');
  const statCoverage = document.getElementById('stat-coverage');
  const warningsBox = document.getElementById('warnings-box');
  const warningsCountText = document.getElementById('warnings-count-text');
  const warningsList = document.getElementById('warnings-list');

  const speedButtons = document.querySelectorAll('.speed-btn');
  const shiftButtons = document.querySelectorAll('.shift-btn');
  const customShiftInput = document.getElementById('custom-shift-value');
  const btnApplyCustomShift = document.getElementById('btn-apply-custom-shift');

  const uploadSection = document.getElementById('upload-section');
  const activeMediaStrip = document.getElementById('active-media-strip');
  const btnToggleUpload = document.getElementById('btn-toggle-upload');
  const btnReopenImport = document.getElementById('btn-reopen-import');
  const btnToggleShifter = document.getElementById('btn-toggle-shifter');
  const timeShiftBar = document.getElementById('time-shift-bar');

  function updateActiveMediaBar() {
    if (state.videoLoaded || state.cues.length > 0) {
      if (activeMediaStrip) activeMediaStrip.style.display = 'flex';
      if (uploadSection) uploadSection.classList.add('collapsed');
      const toggleText = document.getElementById('upload-toggle-text');
      if (toggleText) toggleText.textContent = uploadSection && uploadSection.classList.contains('collapsed') ? 'Import Media' : 'Hide Import';
    }
  }

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

  if (btnToggleShifter) {
    btnToggleShifter.addEventListener('click', () => {
      if (timeShiftBar) timeShiftBar.classList.toggle('show');
    });
  }


  // -------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------
  function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3500);
  }

  function formatSeconds(sec) {
    if (isNaN(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
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
    ts = (ts || '').trim().replace(',', '.');
    const parts = ts.split(':');
    if (parts.length === 3) {
      return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
    } else if (parts.length === 2) {
      return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
    }
    return parseFloat(ts) || 0;
  }

  // -------------------------------------------------------------
  // Tab Switching
  // -------------------------------------------------------------
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

  // -------------------------------------------------------------
  // Video Speed Controller
  // -------------------------------------------------------------
  speedButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      speedButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const rate = parseFloat(btn.dataset.speed);
      video.playbackRate = rate;
      audio.playbackRate = rate;
    });
  });

  // -------------------------------------------------------------
  // Export Dropdown
  // -------------------------------------------------------------
  btnExportDropdown.addEventListener('click', (e) => {
    e.stopPropagation();
    exportMenu.classList.toggle('show');
  });

  document.addEventListener('click', () => {
    exportMenu.classList.remove('show');
  });

  exportMenu.querySelectorAll('.dropdown-item').forEach(item => {
    item.addEventListener('click', async (e) => {
      e.stopPropagation();
      exportMenu.classList.remove('show');
      const format = item.dataset.format;
      await exportSubtitles(format);
    });
  });

  async function exportSubtitles(format) {
    if (!state.cues.length) {
      showToast('No subtitles to export!', 'error');
      return;
    }
    try {
      const response = await fetch('/api/export-subtitles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cues: state.cues, format })
      });
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `subtitles.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast(`Exported as .${format.toUpperCase()}`);
    } catch (err) {
      showToast(`Export error: ${err.message}`, 'error');
    }
  }

  // -------------------------------------------------------------
  // Video Upload & Audio Extraction
  // -------------------------------------------------------------
  videoDropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    videoDropZone.classList.add('dragover');
  });

  videoDropZone.addEventListener('dragleave', () => {
    videoDropZone.classList.remove('dragover');
  });

  videoDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    videoDropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleVideoUpload(e.dataTransfer.files[0]);
    }
  });

  videoFileInput.addEventListener('change', () => {
    if (videoFileInput.files.length) {
      handleVideoUpload(videoFileInput.files[0]);
    }
  });

  async function handleVideoUpload(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);

    videoProgress.style.display = 'flex';
    videoProgressText.textContent = `Uploading "${file.name}" & extracting audio...`;

    try {
      const res = await fetch('/api/upload-video', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || 'Failed to upload video');
      }

      // Update state
      state.videoLoaded = true;
      state.audioLoaded = true;
      state.videoFilename = data.video_filename;
      state.audioFilename = data.audio_filename;
      state.videoDuration = data.duration;
      if (data.project_id) state.projectId = data.project_id;

      // Update UI
      video.src = data.video_url;
      audio.src = data.audio_url;
      btnDownloadAudio.href = data.audio_url;
      btnDownloadAudio.style.display = 'inline-flex';

      videoFileInfo.style.display = 'flex';
      videoNameDisplay.textContent = `${file.name} (${data.video_size_mb} MB)`;

      videoStatusPill.className = 'pill pill-active';
      videoStatusPill.textContent = `Video: ${formatSeconds(data.duration)}`;
      audioStatusPill.className = 'pill pill-active';
      audioStatusPill.textContent = `Audio: MP3 (${data.audio_size_mb} MB)`;

      showToast(`Audio extracted successfully (${data.audio_size_mb} MB)!`);
      initWaveformVisualizer();
      updateActiveMediaBar();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      videoProgress.style.display = 'none';
    }
  }

  // -------------------------------------------------------------
  // Subtitle File Upload & Raw Parser
  // -------------------------------------------------------------
  subsDropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    subsDropZone.classList.add('dragover');
  });

  subsDropZone.addEventListener('dragleave', () => {
    subsDropZone.classList.remove('dragover');
  });

  subsDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    subsDropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleSubtitlesUpload(e.dataTransfer.files[0]);
    }
  });

  subsFileInput.addEventListener('change', () => {
    if (subsFileInput.files.length) {
      handleSubtitlesUpload(subsFileInput.files[0]);
    }
  });

  async function handleSubtitlesUpload(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('video_duration', state.videoDuration || 0.0);

    try {
      const res = await fetch('/api/upload-subtitles-file', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || 'Failed to parse subtitles');
      }

      if (data.subtitle_id) state.subtitleId = data.subtitle_id;
      if (data.project_id) state.projectId = data.project_id;
      applySubtitleData(data.cues, data.stats, data.warnings, file.name);
      showToast(`Loaded ${data.cues.length} subtitles from ${file.name}`);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  btnParseRaw.addEventListener('click', async () => {
    const text = rawSubTextarea.value.trim();
    if (!text) {
      showToast('Please paste subtitle content first.', 'error');
      return;
    }
    try {
      const res = await fetch('/api/parse-subtitles-raw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, video_duration: state.videoDuration || 0.0 })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || 'Failed to parse subtitles');
      }

      if (data.subtitle_id) state.subtitleId = data.subtitle_id;
      applySubtitleData(data.cues, data.stats, data.warnings, 'Pasted Text');
      showToast(`Successfully parsed ${data.cues.length} cues`);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  // -------------------------------------------------------------
  // Load Built-in Demo Sample
  // -------------------------------------------------------------
  btnLoadSample.addEventListener('click', async () => {
    try {
      showToast('Loading demo sample video and subtitles...');
      const res = await fetch('/api/load-sample');
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error('Failed to load sample');
      }

      state.videoLoaded = true;
      state.audioLoaded = true;
      state.videoFilename = data.video_filename;
      state.audioFilename = data.audio_filename;
      state.videoDuration = data.duration;
      if (data.project_id) state.projectId = data.project_id;
      if (data.subtitle_id) state.subtitleId = data.subtitle_id;

      video.src = data.video_url;
      audio.src = data.audio_url;
      btnDownloadAudio.href = data.audio_url;
      btnDownloadAudio.style.display = 'inline-flex';

      videoFileInfo.style.display = 'flex';
      videoNameDisplay.textContent = 'demo_sample.mp4 (Demo)';

      videoStatusPill.className = 'pill pill-active';
      videoStatusPill.textContent = `Video: ${formatSeconds(data.duration)}`;
      audioStatusPill.className = 'pill pill-active';
      audioStatusPill.textContent = 'Audio: MP3 (Ready)';

      applySubtitleData(data.cues, data.stats, data.warnings, 'demo_sample.srt');
      showToast('Demo loaded! Click video to play and watch synced subtitles.');
      initWaveformVisualizer();
      updateActiveMediaBar();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  // -------------------------------------------------------------
  // Apply Subtitle Data to State & UI
  // -------------------------------------------------------------
  function applySubtitleData(cues, stats, warnings, sourceLabel) {
    state.cues = cues;
    state.stats = stats;
    state.warnings = warnings;

    subsFileInfo.style.display = 'flex';
    subsNameDisplay.textContent = sourceLabel;
    subsCueCountBadge.textContent = `${cues.length} Cues`;

    subsStatusPill.className = 'pill pill-active';
    subsStatusPill.textContent = `Subs: ${cues.length} Cues`;

    updateDiagnosticsUI();
    renderCuesList();
    updateActiveMediaBar();
  }

  function updateDiagnosticsUI() {
    statCues.textContent = state.stats.total_cues || state.cues.length || 0;
    statWords.textContent = state.stats.total_words || 0;
    statCps.textContent = state.stats.avg_cps || 0.0;
    statCoverage.textContent = `${state.stats.coverage_percent || 0}%`;

    if (state.warnings && state.warnings.length > 0) {
      warningsBox.style.display = 'block';
      warningsCountText.textContent = `${state.warnings.length} Quality Notices`;
      warningsList.innerHTML = '';
      state.warnings.slice(0, 5).forEach(w => {
        const li = document.createElement('li');
        li.textContent = `Cue #${w.cue_id}: ${w.issues.join(' ')}`;
        warningsList.appendChild(li);
      });
      if (state.warnings.length > 5) {
        const more = document.createElement('li');
        more.textContent = `...and ${state.warnings.length - 5} more`;
        warningsList.appendChild(more);
      }
    } else {
      warningsBox.style.display = 'none';
    }
  }

  // -------------------------------------------------------------
  // Render Cues List
  // -------------------------------------------------------------
  function renderCuesList() {
    cuelistContainer.innerHTML = '';

    if (!state.cues.length) {
      emptyCuesState.style.display = 'flex';
      cuelistContainer.appendChild(emptyCuesState);
      return;
    }

    const query = state.searchQuery.toLowerCase();
    let matchCount = 0;

    state.cues.forEach(cue => {
      const isMatch = query && cue.text.toLowerCase().includes(query);
      if (isMatch) matchCount++;

      const card = document.createElement('div');
      card.className = `cue-card ${isMatch ? 'search-match' : ''} ${state.activeCueId === cue.id ? 'active' : ''}`;
      card.id = `cue-card-${cue.id}`;
      card.dataset.cueId = cue.id;

      const cpsClass = cue.cps > 20 ? 'cps-warn' : 'cps-normal';

      card.innerHTML = `
        <div class="cue-num">#${cue.id}</div>
        <div class="cue-timings">
          <div class="cue-timing-inputs">
            <input type="text" class="time-input start-input" value="${cue.start_formatted || formatTimestamp(cue.start)}" title="Start time">
            <span class="time-arrow">&rarr;</span>
            <input type="text" class="time-input end-input" value="${cue.end_formatted || formatTimestamp(cue.end)}" title="End time">
          </div>
          <div class="cue-meta">
            <span>${cue.duration.toFixed(1)}s</span>
            <span class="cps-pill ${cpsClass}">${cue.cps} cps</span>
          </div>
        </div>
        <div class="cue-text-wrapper">
          <textarea class="cue-text-input" rows="2">${cue.text}</textarea>
        </div>
        <div class="cue-actions">
          <button class="icon-action-btn btn-play-cue" title="Play cue audio/video">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          </button>
          <button class="icon-action-btn btn-clip-audio" title="Clip and download this line's audio">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
          </button>
          <button class="icon-action-btn btn-delete btn-delete-cue" title="Delete cue">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      `;

      // Event: Seek on click
      card.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.closest('button')) {
          return; // Allow editing without forcing seek
        }
        seekToCue(cue.start);
      });

      // Event: Text edit
      const textarea = card.querySelector('.cue-text-input');
      textarea.addEventListener('input', () => {
        cue.text = textarea.value;
        cue.char_count = cue.text.length;
        cue.word_count = cue.text.split(/\s+/).filter(Boolean).length;
        cue.cps = parseFloat((cue.char_count / cue.duration).toFixed(1));
        recalcStatsLocally();
      });

      // Event: Timing inputs edit
      const startInp = card.querySelector('.start-input');
      const endInp = card.querySelector('.end-input');

      const handleTimeChange = () => {
        const newStart = parseFormattedTimestamp(startInp.value);
        const newEnd = parseFormattedTimestamp(endInp.value);
        if (newEnd > newStart) {
          cue.start = Math.max(0, newStart);
          cue.end = newEnd;
          cue.duration = parseFloat((cue.end - cue.start).toFixed(2));
          cue.start_formatted = formatTimestamp(cue.start);
          cue.end_formatted = formatTimestamp(cue.end);
          cue.cps = parseFloat((cue.char_count / cue.duration).toFixed(1));
          renderCuesList();
    updateActiveMediaBar();
        }
      };

      startInp.addEventListener('blur', handleTimeChange);
      endInp.addEventListener('blur', handleTimeChange);

      // Event: Play Line preview
      card.querySelector('.btn-play-cue').addEventListener('click', (e) => {
        e.stopPropagation();
        playCueSegment(cue.start, cue.end);
      });

      // Event: Clip Audio snippet
      card.querySelector('.btn-clip-audio').addEventListener('click', (e) => {
        e.stopPropagation();
        clipCueAudio(cue);
      });

      // Event: Delete cue
      card.querySelector('.btn-delete-cue').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteCue(cue.id);
      });

      cuelistContainer.appendChild(card);
    });

    if (query) {
      searchMatchesBadge.style.display = 'inline-block';
      searchMatchesBadge.textContent = `${matchCount} match${matchCount === 1 ? '' : 'es'}`;
    } else {
      searchMatchesBadge.style.display = 'none';
    }
  }

  function seekToCue(timeSec) {
    video.currentTime = timeSec;
    if (audio.src) audio.currentTime = timeSec;
  }

  function playCueSegment(start, end) {
    seekToCue(start);
    video.play();
    if (audio.src) audio.play();

    const checkInterval = setInterval(() => {
      if (video.currentTime >= end || video.paused) {
        video.pause();
        if (audio.src) audio.pause();
        clearInterval(checkInterval);
      }
    }, 100);
  }

  async function clipCueAudio(cue) {
    if (!state.audioFilename) {
      showToast('No audio track available to clip!', 'error');
      return;
    }
    try {
      showToast(`Extracting audio snippet for cue #${cue.id}...`);
      const res = await fetch('/api/clip-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audio_filename: state.audioFilename,
          start: cue.start,
          end: cue.end
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || 'Clip failed');
      }

      // Trigger download
      const a = document.createElement('a');
      a.href = data.clip_url;
      a.download = data.clip_filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast(`Audio clip #${cue.id} downloaded (${data.duration}s)!`);
    } catch (err) {
      showToast(`Clip error: ${err.message}`, 'error');
    }
  }

  function deleteCue(cueId) {
    state.cues = state.cues.filter(c => c.id !== cueId);
    // Renumber cues
    state.cues.forEach((c, idx) => c.id = idx + 1);
    recalcStatsLocally();
    renderCuesList();
    updateActiveMediaBar();
    showToast('Subtitle cue deleted');
  }

  function recalcStatsLocally() {
    const totalSpeech = state.cues.reduce((acc, c) => acc + c.duration, 0);
    const totalWords = state.cues.reduce((acc, c) => acc + c.word_count, 0);
    const totalChars = state.cues.reduce((acc, c) => acc + c.char_count, 0);
    const avgCps = totalSpeech > 0 ? (totalChars / totalSpeech).toFixed(1) : 0;
    const coverage = state.videoDuration > 0 ? ((totalSpeech / state.videoDuration) * 100).toFixed(1) : 0;

    state.stats = {
      total_cues: state.cues.length,
      total_speech_duration: totalSpeech.toFixed(2),
      total_words: totalWords,
      total_characters: totalChars,
      avg_cps: avgCps,
      coverage_percent: Math.min(100, coverage)
    };
    updateDiagnosticsUI();
  }

  // -------------------------------------------------------------
  // Add Cue at Playhead
  // -------------------------------------------------------------
  btnAddCue.addEventListener('click', () => {
    const currentTime = video.currentTime || 0;
    const duration = 2.5;
    const newCue = {
      id: state.cues.length + 1,
      start: parseFloat(currentTime.toFixed(3)),
      end: parseFloat((currentTime + duration).toFixed(3)),
      duration: duration,
      text: 'New subtitle dialogue...',
      start_formatted: formatTimestamp(currentTime),
      end_formatted: formatTimestamp(currentTime + duration),
      char_count: 24,
      word_count: 3,
      cps: parseFloat((24 / duration).toFixed(1))
    };

    // Insert sorted by start time
    state.cues.push(newCue);
    state.cues.sort((a, b) => a.start - b.start);
    state.cues.forEach((c, i) => c.id = i + 1);

    recalcStatsLocally();
    renderCuesList();
    updateActiveMediaBar();

    const newCard = document.getElementById(`cue-card-${newCue.id}`);
    if (newCard) {
      newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const txt = newCard.querySelector('.cue-text-input');
      if (txt) txt.focus();
    }
    showToast(`Added cue at ${formatTimestamp(currentTime)}`);
  });

  // -------------------------------------------------------------
  // Search Dialogue
  // -------------------------------------------------------------
  subtitleSearch.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.trim();
    renderCuesList();
    updateActiveMediaBar();
  });

  // -------------------------------------------------------------
  // Time Shift Tools
  // -------------------------------------------------------------
  shiftButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const delta = parseFloat(btn.dataset.shift);
      await applyTimeShift(delta);
    });
  });

  btnApplyCustomShift.addEventListener('click', async () => {
    const delta = parseFloat(customShiftInput.value);
    if (isNaN(delta) || delta === 0) {
      showToast('Enter a valid shift delta (e.g. +0.5 or -0.5)', 'error');
      return;
    }
    await applyTimeShift(delta);
  });

  async function applyTimeShift(delta) {
    if (!state.cues.length) {
      showToast('No subtitles loaded to shift.', 'error');
      return;
    }
    try {
      const res = await fetch('/api/shift-subtitles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cues: state.cues,
          delta: delta,
          video_duration: state.videoDuration || 0.0,
          subtitle_id: state.subtitleId
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || 'Failed to shift timestamps');
      }

      state.cues = data.cues;
      state.stats = data.stats;
      state.warnings = data.warnings;
      updateDiagnosticsUI();
      renderCuesList();
    updateActiveMediaBar();
      showToast(`Shifted all subtitles by ${delta > 0 ? '+' : ''}${delta}s`);
    } catch (err) {
      showToast(`Shift error: ${err.message}`, 'error');
    }
  }

  // -------------------------------------------------------------
  // Save Subtitles to SQLite Database
  // -------------------------------------------------------------
  if (btnSaveDb) {
    btnSaveDb.addEventListener('click', async () => {
      if (!state.cues.length) {
        showToast('No subtitles loaded to save!', 'error');
        return;
      }
      try {
        let res;
        if (state.subtitleId) {
          res = await fetch(`/api/subtitles/${state.subtitleId}/save`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              cues: state.cues,
              video_duration: state.videoDuration || 0.0
            })
          });
        } else {
          const srtText = state.cues.map((c, i) => `${i + 1}\n${c.start_formatted || formatTimestamp(c.start)} --> ${c.end_formatted || formatTimestamp(c.end)}\n${c.text}\n`).join('\n');
          res = await fetch('/api/parse-subtitles-raw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: srtText,
              video_duration: state.videoDuration || 0.0,
              project_id: state.projectId
            })
          });
        }
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || 'Failed to save to database');
        }
        if (data.subtitle_id) state.subtitleId = data.subtitle_id;
        showToast('Subtitles saved to SQLite database successfully!');
      } catch (err) {
        showToast(`Save error: ${err.message}`, 'error');
      }
    });
  }

  // -------------------------------------------------------------
  // Video & Subtitle Playback Sync
  // -------------------------------------------------------------
  video.addEventListener('timeupdate', () => {
    const curTime = video.currentTime;

    // Synchronize audio scrubber and display
    audioScrubber.value = (curTime / (video.duration || 1)) * 100;
    audioTimeDisplay.textContent = `${formatSeconds(curTime)} / ${formatSeconds(video.duration || 0)}`;

    // Sync audio element if playing
    if (audio.src && Math.abs(audio.currentTime - curTime) > 0.3) {
      audio.currentTime = curTime;
    }

    // Find active subtitle cue
    let activeCue = null;
    for (const cue of state.cues) {
      if (curTime >= cue.start && curTime <= cue.end) {
        activeCue = cue;
        break;
      }
    }

    if (activeCue) {
      videoOverlay.style.display = 'block';
      videoSubText.textContent = activeCue.text;

      if (state.activeCueId !== activeCue.id) {
        state.activeCueId = activeCue.id;

        // Update active class in cue cards
        document.querySelectorAll('.cue-card').forEach(c => c.classList.remove('active'));
        const activeCard = document.getElementById(`cue-card-${activeCue.id}`);
        if (activeCard) {
          activeCard.classList.add('active');
          activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    } else {
      videoOverlay.style.display = 'none';
      if (state.activeCueId !== null) {
        state.activeCueId = null;
        document.querySelectorAll('.cue-card').forEach(c => c.classList.remove('active'));
      }
    }
  });

  video.addEventListener('play', () => {
    if (audio.src && audio.paused) audio.play().catch(() => {});
    audioPlayIcon.style.display = 'none';
    audioPauseIcon.style.display = 'block';
  });

  video.addEventListener('pause', () => {
    if (audio.src && !audio.paused) audio.pause();
    audioPlayIcon.style.display = 'block';
    audioPauseIcon.style.display = 'none';
  });

  btnAudioPlay.addEventListener('click', () => {
    if (video.paused) {
      video.play();
    } else {
      video.pause();
    }
  });

  audioScrubber.addEventListener('input', (e) => {
    const targetPercent = parseFloat(e.target.value);
    const targetTime = (targetPercent / 100) * (video.duration || 1);
    video.currentTime = targetTime;
    if (audio.src) audio.currentTime = targetTime;
  });

  // -------------------------------------------------------------
  // Waveform Visualizer
  // -------------------------------------------------------------
  function initWaveformVisualizer() {
    function draw() {
      requestAnimationFrame(draw);
      const width = waveformCanvas.width;
      const height = waveformCanvas.height;
      canvasCtx.clearRect(0, 0, width, height);

      const isPlaying = !video.paused;
      const bars = 64;
      const barWidth = (width / bars) - 2;

      for (let i = 0; i < bars; i++) {
        let barHeight;
        if (isPlaying) {
          // Dynamic simulated frequency waves
          const time = Date.now() * 0.005;
          const wave = Math.sin(time + (i * 0.2)) * Math.cos(time * 0.5 + (i * 0.1));
          barHeight = Math.max(4, Math.abs(wave) * (height * 0.85));
        } else {
          // Subtle idle resting pattern
          barHeight = Math.sin(i * 0.3) * 6 + 10;
        }

        const x = i * (barWidth + 2);
        const y = (height - barHeight) / 2;

        const gradient = canvasCtx.createLinearGradient(0, y, 0, y + barHeight);
        gradient.addColorStop(0, '#06b6d4');
        gradient.addColorStop(1, '#6366f1');

        canvasCtx.fillStyle = gradient;
        canvasCtx.beginPath();
        canvasCtx.roundRect(x, y, barWidth, barHeight, 2);
        canvasCtx.fill();
      }
    }
    draw();
  }

  // Initial call to draw resting waveform
  initWaveformVisualizer();
      updateActiveMediaBar();
});
