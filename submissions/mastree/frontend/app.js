/**
 * MasteryLoop — Adaptive AI Classroom
 * Vanilla JS frontend wired to FastAPI backend.
 *
 * API shapes (confirmed against live endpoints):
 *   POST /api/login          -> {student_id, username, created_at}
 *   GET  /api/courses        -> {courses: [{concept_id, name, description, seq_order, is_custom, prereqs}]}
 *   POST /api/search         -> {results: [{id, title, snippet, source, url}], web_search_unavailable, note}
 *   POST /api/ingest         -> {job_id}
 *   POST /api/ingest/upload  -> {job_id}
 *   GET  /api/ingest/{id}    -> {status, step, progress, message, concept_id, chunk_count, chunks_preview}
 *   POST /api/lesson         -> {lesson_id, concept_id, concept_name, style, format, scenes: [{title, narration, bullets, key_term, citations, visual}]}
 *   POST /api/quiz/generate  -> {concept_id, questions: [{question_id, question_text, option_a, option_b, option_c, option_d, difficulty, source_chunk_id}]}
 *   POST /api/quiz/answer    -> {results: [{question_id, is_correct, correct_letter, explanation, citation_chunk_id}]}
 *   POST /api/gate           -> {gate_passed, mastery_score, attempt_count, distinct_difficulties, reason, root_cause?, next_concept?, loop_count, needs_human_help, next_style, event_id}
 *   GET  /api/progress/{id}  -> {progress, history}
 *   GET  /api/why/{id}       -> {event_id, sql_query, prereq_rows}
 *   POST /api/admin/reset    -> {message}
 */

(function () {
  'use strict';

  // ================================================================
  // STATE
  // ================================================================
  const state = {
    currentStep: 1,
    student_id: null,
    username: null,
    activeTopic: null,
    concept_id: null,
    theme: 'dark',
    format: 'board',
    currentStyle: 'step-by-step',
    remediationLoop: 1,
    currentJobId: null,
    jobPollInterval: null,
    lesson: null,
    currentSceneIdx: 0,
    isPlaying: false,
    speechRate: 1.0,
    isMuted: false,
    quizQuestions: [],
    currentQuestionIdx: 0,
    hasSubmittedCurrent: false,
    userAnswers: [],
    gateResult: null,
    lastEventId: null,
    coursesList: []
  };

  // ================================================================
  // DOM REFS
  // ================================================================
  const screens   = {};
  [1,2,3,4,5,6,7,8].forEach(n => {
    screens[n] = document.getElementById(`screen-${['login','source','ingest','format','classroom','assessment','gate','ledger'][n-1]}`);
  });
  const navItems       = document.querySelectorAll('.step-item');
  const userLabel      = document.getElementById('user-label');
  const topicTitle     = document.getElementById('topic-title');
  const errorBanner    = document.getElementById('error-banner');
  const errorMsgText   = document.getElementById('error-message-text');
  const btnCloseError  = document.getElementById('btn-close-error');
  const db2StatusEl    = document.getElementById('db2-status');

  // ================================================================
  // UTILITIES
  // ================================================================
  function esc(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  let _notifTimer = null;
  function notify(msg, ok = false) {
    if (!errorBanner || !errorMsgText) return;
    errorMsgText.textContent = msg;
    errorBanner.style.borderColor = ok ? 'var(--emerald-border)' : 'var(--amber-border)';
    errorBanner.classList.add('show');
    if (_notifTimer) clearTimeout(_notifTimer);
    _notifTimer = setTimeout(() => errorBanner.classList.remove('show'), 7000);
  }
  if (btnCloseError) btnCloseError.addEventListener('click', () => errorBanner.classList.remove('show'));

  async function api(endpoint, method = 'GET', body = null, isForm = false) {
    const opts = { method };
    if (body) {
      if (isForm) { opts.body = body; }
      else { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
    }
    const res = await fetch(endpoint, opts);
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail || json.error || `HTTP ${res.status}`);
    return json;
  }

  // ================================================================
  // NAVIGATION
  // ================================================================
  function goTo(step) {
    if (step < 1 || step > 8) return;
    state.currentStep = step;
    Object.entries(screens).forEach(([k, el]) => {
      if (el) el.classList.toggle('active', parseInt(k) === step);
    });
    navItems.forEach(item => {
      const s = parseInt(item.getAttribute('data-step'));
      item.classList.toggle('active', s === step);
      item.classList.toggle('completed', s < step);
    });
    const canvas = document.getElementById('workspace-canvas');
    if (canvas) canvas.scrollTop = 0;
    if (step === 8 && state.student_id) loadProgress();
  }

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const s = parseInt(item.getAttribute('data-step'));
      if (s > 1 && !state.student_id) { notify('Please log in first.'); return; }
      goTo(s);
    });
  });

  function setTopic(name) {
    state.activeTopic = name;
    if (topicTitle) topicTitle.innerHTML =
      `<span>MasteryLoop</span><span class="crumb-sep">/</span><span class="active-crumb">${esc(name)}</span>`;
  }

  // ================================================================
  // THEME
  // ================================================================
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon   = document.getElementById('theme-icon');
  const themeLabel  = document.getElementById('theme-label');

  function applyTheme() {
    const dark = state.theme === 'dark';
    document.body.classList.toggle('dark-theme', dark);
    document.body.classList.toggle('light-theme', !dark);
    if (themeLabel) themeLabel.textContent = dark ? 'Obsidian' : 'Swiss Light';
    if (themeIcon) themeIcon.innerHTML = dark
      ? '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>'
      : '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line>';
  }
  if (themeToggle) themeToggle.addEventListener('click', () => {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme();
  });
  applyTheme();

  // ================================================================
  // STARTUP — check DB2 + load courses
  // ================================================================
  async function init() {
    try {
      const data = await api('/api/courses');
      state.coursesList = data.courses || [];
      setDb2Status(true);
      renderCoursesGrid(state.coursesList);
      populatePrereqSelect(state.coursesList);
    } catch (e) {
      setDb2Status(false);
      notify('Db2 connection failed: ' + e.message);
    }
  }

  function setDb2Status(online) {
    if (!db2StatusEl) return;
    db2StatusEl.innerHTML = online
      ? `<div style="display:flex;align-items:center;gap:8px;">
           <span class="status-dot online"></span>
           <span style="font-weight:600;color:var(--text);">IBM Db2 Online</span>
         </div>
         <div style="font-size:10px;color:var(--text-dim);margin-top:2px;">ACID Vector Engine • LUW</div>`
      : `<div style="display:flex;align-items:center;gap:8px;">
           <span class="status-dot offline"></span>
           <span style="font-weight:600;color:var(--rose);">Db2 Disconnected</span>
         </div>
         <div style="font-size:10px;color:var(--text-dim);margin-top:2px;">Check .env settings</div>`;
  }

  // ================================================================
  // CLEAN DB BUTTON
  // ================================================================
  const btnResetDb = document.getElementById('btn-reset-db');
  if (btnResetDb) {
    btnResetDb.addEventListener('click', async () => {
      if (!confirm('Wipe ALL data from IBM Db2? This clears concepts, chunks, lessons, quiz attempts, students, and mastery records completely.')) return;
      btnResetDb.querySelector('span') && (btnResetDb.querySelector('span').textContent = 'Clearing...');
      try {
        await api('/api/admin/reset', 'POST', { wipe_all: true });
        state.student_id = null;
        state.username = null;
        state.concept_id = null;
        state.activeTopic = null;
        state.lastEventId = null;
        state.remediationLoop = 1;
        state.lesson = null;
        state.coursesList = [];
        if (userLabel) userLabel.innerHTML = '<span class="user-avatar">?</span><span>Guest</span>';
        if (topicTitle) topicTitle.innerHTML = '<span>MasteryLoop</span><span class="crumb-sep">/</span><span class="active-crumb">Select a Topic</span>';
        renderCoursesGrid([]);
        populatePrereqSelect([]);
        await init();
        notify('Database cleared. Please enter a student handle to begin freshly.', true);
        goTo(1);
      } catch (e) {
        notify('Reset failed: ' + e.message);
      } finally {
        if (btnResetDb.querySelector('span')) btnResetDb.querySelector('span').textContent = 'Clean DB';
      }
    });
  }

  // ================================================================
  // SCREEN 1 — LOGIN
  // ================================================================
  const usernameInput = document.getElementById('username');
  const btnLogin      = document.getElementById('btn-login');

  async function doLogin() {
    const val = usernameInput ? usernameInput.value.trim() : '';
    if (!val) { notify('Enter a student handle.'); return; }
    if (btnLogin) { btnLogin.textContent = 'Connecting...'; btnLogin.disabled = true; }
    try {
      const r = await api('/api/login', 'POST', { username: val });
      state.student_id = r.student_id;
      state.username   = r.username;
      if (userLabel) userLabel.innerHTML =
        `<span class="user-avatar">${val.charAt(0).toUpperCase()}</span><span>${esc(val)}</span>`;
      notify(`Session active for ${val}.`, true);
      goTo(2);
    } catch (e) {
      notify('Login error: ' + e.message);
    } finally {
      if (btnLogin) { btnLogin.textContent = 'Start Learning Session →'; btnLogin.disabled = false; }
    }
  }

  if (btnLogin)      btnLogin.addEventListener('click', doLogin);
  if (usernameInput) usernameInput.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });

  // ================================================================
  // SCREEN 2 — SOURCE SELECTION
  // ================================================================
  // --- Tab switching ---
  function setSourceTab(tab) {
    ['search','upload','course'].forEach(t => {
      const btn = document.getElementById(`tab-${t}`);
      const pnl = document.getElementById(`panel-${t}`);
      if (btn) btn.classList.toggle('active', t === tab);
      if (pnl) pnl.classList.toggle('active', t === tab);
    });
  }
  ['search','upload','course'].forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    if (btn) btn.addEventListener('click', () => setSourceTab(t));
  });

  // --- Tab A: Internet Search, AI Knowledge Base & Direct URL ---
  const searchQueryEl   = document.getElementById('search-query');
  const optWikiEl       = document.getElementById('opt-web');
  const searchResultsEl = document.getElementById('search-results');
  const btnSearch       = document.getElementById('btn-search');
  const btnAiKb         = document.getElementById('btn-ai-kb');
  const directUrlEl     = document.getElementById('direct-url-input');
  const btnFetchUrl     = document.getElementById('btn-fetch-url');

  async function doSearch() {
    const q = searchQueryEl ? searchQueryEl.value.trim() : '';
    if (!q) { notify('Enter a search term.'); return; }
    if (btnSearch) { btnSearch.textContent = 'Searching...'; btnSearch.disabled = true; }
    if (searchResultsEl) searchResultsEl.innerHTML =
      `<div style="padding:24px;text-align:center;color:var(--text-muted);">Searching across the internet…</div>`;
    try {
      const data = await api('/api/search', 'POST', {
        query: q,
        include_web: true,
        include_wikipedia: optWikiEl ? optWikiEl.checked : false
      });
      if (data.web_search_unavailable) {
        notify('Live web search had an issue; you can use AI Knowledge Base or Paste URL directly.');
      }
      renderSearchResults(Array.isArray(data.results) ? data.results : []);
    } catch (e) {
      notify('Search error: ' + e.message);
      if (searchResultsEl) searchResultsEl.innerHTML =
        `<div style="padding:24px;text-align:center;color:var(--rose);">Search failed: ${esc(e.message)}</div>`;
    } finally {
      if (btnSearch) { btnSearch.textContent = 'Search Web'; btnSearch.disabled = false; }
    }
  }

  if (btnSearch)     btnSearch.addEventListener('click', doSearch);
  if (searchQueryEl) searchQueryEl.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  if (btnAiKb) {
    btnAiKb.addEventListener('click', () => {
      const q = searchQueryEl ? searchQueryEl.value.trim() : '';
      if (!q) { notify('Enter a topic name first to generate from Gemini Knowledge Base.'); return; }
      ingest({
        source_type: 'ai_kb',
        topic_name: q,
        replace_existing: true
      });
    });
  }

  if (btnFetchUrl) {
    btnFetchUrl.addEventListener('click', () => {
      const urlVal = directUrlEl ? directUrlEl.value.trim() : '';
      if (!urlVal || !urlVal.startsWith('http')) {
        notify('Enter a valid URL starting with http:// or https://');
        return;
      }
      const q = searchQueryEl ? searchQueryEl.value.trim() : '';
      const slug = urlVal.split('/').filter(Boolean).pop() || 'Web Article';
      const topic = q || slug.replace(/[-_]+/g, ' ').replace(/\.[a-z0-9]+$/i, '');
      ingest({
        source_type: 'url',
        topic_name: topic,
        url: urlVal,
        replace_existing: true
      });
    });
  }

  function renderSearchResults(items) {
    if (!searchResultsEl) return;
    if (!items.length) {
      searchResultsEl.innerHTML =
        `<div style="padding:24px;text-align:center;color:var(--text-muted);">No web results returned. Click <strong>AI Knowledge Base</strong> above to generate study content directly, or paste a URL below.</div>`;
      return;
    }
    searchResultsEl.innerHTML = items.map(item => {
      const isWiki = (item.url || '').toLowerCase().includes('wikipedia.org') || item.source === 'wikipedia';
      return `
      <div class="result-card">
        <div class="result-main">
          <div class="result-title">
            <span>${esc(item.title)}</span>
            <span class="badge badge-db2">${esc(item.source || 'web')}</span>
          </div>
          <p class="result-snippet">${esc(item.snippet)}</p>
          ${item.url ? `<div style="font-size:10.5px;font-family:'JetBrains Mono',monospace;color:var(--text-dim);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:520px;">${esc(item.url)}</div>` : ''}
        </div>
        <button class="btn btn-secondary btn-sm btn-use-source"
                data-title="${esc(item.title)}"
                data-source="${isWiki ? 'wikipedia' : 'web'}"
                data-url="${esc(item.url || '')}"
                data-text="${esc(item.full_text || '')}">
          Use this Source →
        </button>
      </div>`;
    }).join('');

    searchResultsEl.querySelectorAll('.btn-use-source').forEach(btn => {
      btn.addEventListener('click', () => {
        const textVal = btn.getAttribute('data-text');
        const payload = {
          source_type: btn.getAttribute('data-source'),
          topic_name:  btn.getAttribute('data-title'),
          url:         btn.getAttribute('data-url'),
          replace_existing: true
        };
        if (textVal) payload.text = textVal;
        ingest(payload);
      });
    });
  }

  // --- Tab B: Upload / Paste ---
  const dropZoneEl    = document.getElementById('drop-zone');
  const fileInputEl   = document.getElementById('file-input');
  const pasteTextEl   = document.getElementById('paste-text');
  const topicNameEl   = document.getElementById('topic-name');
  const prereqSelectEl = document.getElementById('prereq-select');
  const btnUpload     = document.getElementById('btn-ingest-upload');
  let selectedFile    = null;

  if (dropZoneEl && fileInputEl) {
    dropZoneEl.addEventListener('click', () => fileInputEl.click());
    dropZoneEl.addEventListener('dragover', e => { e.preventDefault(); dropZoneEl.classList.add('dragover'); });
    dropZoneEl.addEventListener('dragleave', () => dropZoneEl.classList.remove('dragover'));
    dropZoneEl.addEventListener('drop', e => {
      e.preventDefault(); dropZoneEl.classList.remove('dragover');
      if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInputEl.addEventListener('change', () => { if (fileInputEl.files.length) handleFile(fileInputEl.files[0]); });
  }

  function handleFile(f) {
    selectedFile = f;
    if (dropZoneEl) dropZoneEl.innerHTML =
      `<svg fill="none" height="22" stroke="var(--emerald)" stroke-width="2" viewBox="0 0 24 24" width="22"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
       <span style="font-weight:600;color:var(--text);">${esc(f.name)}</span>
       <span style="font-size:11.5px;color:var(--text-muted);">Click or drop another file to replace</span>`;
    if (topicNameEl && !topicNameEl.value.trim())
      topicNameEl.value = f.name.replace(/\.[^/.]+$/, '');
  }

  function populatePrereqSelect(courses) {
    if (!prereqSelectEl) return;
    prereqSelectEl.innerHTML = courses.length
      ? courses.map(c => `<option value="${c.concept_id}">${esc(c.name)}</option>`).join('')
      : '<option disabled>No existing topics</option>';
  }

  if (btnUpload) {
    btnUpload.addEventListener('click', async () => {
      const topic = topicNameEl ? topicNameEl.value.trim() : '';
      const text  = pasteTextEl ? pasteTextEl.value.trim() : '';
      if (!topic) { notify('Provide a Topic Name.'); return; }
      if (!selectedFile && !text) { notify('Attach a file (.txt/.md/.pdf) or paste notes.'); return; }
      btnUpload.textContent = 'Uploading…'; btnUpload.disabled = true;
      try {
        const form = new FormData();
        if (selectedFile) form.append('file', selectedFile);
        if (text) form.append('text', text);
        form.append('topic_name', topic);
        if (state.student_id) form.append('student_id', state.student_id);
        if (prereqSelectEl) {
          const pids = Array.from(prereqSelectEl.selectedOptions).map(o => o.value).filter(Boolean);
          if (pids.length) form.append('prereq_ids', JSON.stringify(pids.map(Number)));
        }
        const r = await api('/api/ingest/upload', 'POST', form, true);
        selectedFile = null;
        if (fileInputEl) fileInputEl.value = '';
        if (dropZoneEl) dropZoneEl.innerHTML =
          '<p style="font-weight:600; margin-bottom:4px; font-size:13px;">Drag study notes here or click to browse</p>' +
          '<p style="color:var(--text-muted); font-size:11.5px; font-family:\'JetBrains Mono\',monospace;">.txt, .md, .pdf (maximum 15MB)</p>';
        setTopic(topic);
        startPoll(r.job_id);
        goTo(3);
      } catch (e) {
        notify('Upload error: ' + e.message);
      } finally {
        btnUpload.textContent = 'Extract Chunks & Vectorize into Db2 →'; btnUpload.disabled = false;
      }
    });
  }

  // --- Tab C: Course Grid ---
  function renderCoursesGrid(courses) {
    const grid = document.getElementById('course-grid');
    if (!grid) return;
    if (!courses.length) {
      grid.innerHTML =
        `<div style="grid-column:1/-1;padding:32px;text-align:center;color:var(--text-muted);">
           No curriculum concepts in Db2. Use Search or Attach Notes to ingest your own topics.
         </div>`;
      return;
    }
    grid.innerHTML = courses.map(c => `
      <div class="course-card" data-cid="${c.concept_id}" data-cname="${esc(c.name)}" data-chunks="${c.chunk_count || 0}">
        <div class="course-code">${c.is_custom ? 'CUSTOM' : `SEQ #${c.seq_order}`} &bull; ${c.chunk_count || 0} CHUNKS</div>
        <div class="course-name">${esc(c.name)}</div>
        <p class="course-desc">${esc(c.description || '')}</p>
      </div>`).join('');

    grid.querySelectorAll('.course-card').forEach(card => {
      card.addEventListener('click', () => {
        grid.querySelectorAll('.course-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        const cid    = parseInt(card.getAttribute('data-cid'));
        const cname  = card.getAttribute('data-cname');
        const chunks = parseInt(card.getAttribute('data-chunks') || '0');
        state.concept_id = cid;
        state.remediationLoop = 1;
        state.currentStyle = 'step-by-step';
        setTopic(cname);
        if (chunks > 0) {
          notify(`Loaded '${cname}' (${chunks} verified chunks in Db2). Choose your learning format.`, true);
          goTo(4);
        } else {
          ingest({ source_type: 'course', topic_name: cname });
        }
      });
    });
  }

  // ================================================================
  // INGESTION — shared helper
  // ================================================================
  async function ingest(payload) {
    payload.student_id = state.student_id;
    state.remediationLoop = 1;
    state.currentStyle = 'step-by-step';
    if (prereqSelectEl && !payload.prereq_ids) {
      const pids = Array.from(prereqSelectEl.selectedOptions).map(o => parseInt(o.value)).filter(n => !isNaN(n));
      if (pids.length) payload.prereq_ids = pids;
    }
    setTopic(payload.topic_name);
    try {
      const r = await api('/api/ingest', 'POST', payload);
      startPoll(r.job_id);
      goTo(3);
    } catch (e) {
      notify('Ingest error: ' + e.message);
    }
  }

  // ================================================================
  // SCREEN 3 — INGESTION TELEMETRY POLLING
  // ================================================================
  const ingestBarEl     = document.getElementById('ingest-bar');
  const ingestSummaryEl = document.getElementById('ingest-summary-text');
  const chunkPreviewEl  = document.getElementById('chunk-preview');
  const btnGotoFormat   = document.getElementById('btn-goto-format');
  const trackerSteps    = document.querySelectorAll('.tracker-step');

  function startPoll(jobId) {
    state.currentJobId = jobId;
    if (state.jobPollInterval) clearInterval(state.jobPollInterval);
    if (btnGotoFormat) btnGotoFormat.disabled = true;
    trackerSteps.forEach((st, i) => {
      st.className = 'tracker-step' + (i === 0 ? ' active' : '');
      const b = st.querySelector('.tracker-bubble');
      if (b) b.textContent = String(i + 1);
    });
    if (ingestBarEl) ingestBarEl.style.width = '5%';
    if (ingestSummaryEl) ingestSummaryEl.textContent = 'Starting ingestion…';
    if (chunkPreviewEl) {
      const tbody = chunkPreviewEl.querySelector('tbody');
      if (tbody) tbody.innerHTML = '';
    }

    state.jobPollInterval = setInterval(async () => {
      try {
        const job = await api(`/api/ingest/${jobId}`);
        updateIngestUI(job);
        if (job.status === 'completed') {
          clearInterval(state.jobPollInterval);
          state.concept_id = job.concept_id;
          state.remediationLoop = 1;
          if (btnGotoFormat) btnGotoFormat.disabled = false;
          notify(`Stored ${job.chunk_count} chunks in IBM Db2 (${job.source_label || state.activeTopic}).`, true);
          init();
        } else if (job.status === 'failed') {
          clearInterval(state.jobPollInterval);
          notify('Ingestion failed: ' + (job.error || 'unknown error'));
        }
      } catch (e) {
        clearInterval(state.jobPollInterval);
        notify('Poll error: ' + e.message);
      }
    }, 800);
  }

  const STEP_IDX = { 'Fetching content': 0, 'Chunking text': 1, 'Embedding chunks': 2, 'Persisting to Db2': 3 };

  function updateIngestUI(job) {
    if (ingestBarEl) ingestBarEl.style.width = `${job.progress || 10}%`;
    if (ingestSummaryEl) {
      const labelSuffix = job.source_label ? ` • ${job.source_label}` : '';
      ingestSummaryEl.textContent = (job.message || 'Processing…') + labelSuffix;
    }

    const curIdx = job.status === 'completed' ? 4 : (STEP_IDX[job.step] ?? 0);
    trackerSteps.forEach((st, i) => {
      const done = i < curIdx || job.status === 'completed';
      st.className = 'tracker-step' + (done ? ' completed' : i === curIdx ? ' active' : '');
      const b = st.querySelector('.tracker-bubble');
      if (b) b.textContent = done ? '✓' : String(i + 1);
    });

    if (chunkPreviewEl && Array.isArray(job.chunks_preview) && job.chunks_preview.length) {
      const tbody = chunkPreviewEl.querySelector('tbody') || chunkPreviewEl;
      tbody.innerHTML = job.chunks_preview.slice(0, 5).map((ch, i) => {
        const isObj = ch && typeof ch === 'object';
        const idxLabel = String((isObj ? (ch.chunk_index || ch.chunk_id) : null) || (i + 1)).padStart(3, '0');
        const txt = isObj ? (ch.text || '') : String(ch || '');
        const wc = isObj && ch.word_count ? ch.word_count : txt.split(/\s+/).filter(Boolean).length;
        return `
          <tr>
            <td style="font-family:'JetBrains Mono',monospace;">CHUNK_${idxLabel}</td>
            <td>${esc(txt.slice(0, 120))}</td>
            <td style="font-family:'JetBrains Mono',monospace;">${wc}w</td>
            <td><span class="badge badge-success">${job.status === 'completed' ? 'Stored in Db2' : 'Prepared'}</span></td>
          </tr>`;
      }).join('');
    }
  }

  if (btnGotoFormat) btnGotoFormat.addEventListener('click', () => goTo(4));

  // ================================================================
  // SCREEN 4 — FORMAT SELECTION
  // ================================================================
  const fmtBoard    = document.getElementById('fmt-board');
  const fmtVideo    = document.getElementById('fmt-video');
  const btnStartLesson = document.getElementById('btn-start-lesson');

  if (fmtBoard && fmtVideo) {
    fmtBoard.addEventListener('click', () => {
      state.format = 'board'; fmtBoard.classList.add('selected'); fmtVideo.classList.remove('selected');
    });
    fmtVideo.addEventListener('click', () => {
      state.format = 'video'; fmtVideo.classList.add('selected'); fmtBoard.classList.remove('selected');
    });
  }

  if (btnStartLesson) {
    btnStartLesson.addEventListener('click', async () => {
      if (!state.concept_id) { notify('No topic selected. Go back to Source.'); return; }
      btnStartLesson.textContent = 'Synthesising from Db2 chunks…'; btnStartLesson.disabled = true;
      try {
        const data = await api('/api/lesson', 'POST', {
          student_id: state.student_id,
          concept_id: state.concept_id,
          format:     state.format,
          style:      state.currentStyle,
          loop_count: state.remediationLoop
        });
        state.lesson = data;
        if (data.used_fallback) {
          notify(`Live AI fallback notice: ${data.fallback_reason || 'Using chunk-extracted lesson scenes.'}`);
        }
        goTo(5);
        renderClassroom();
      } catch (e) {
        notify('Lesson error: ' + e.message);
      } finally {
        btnStartLesson.textContent = 'Launch Adaptive Classroom →'; btnStartLesson.disabled = false;
      }
    });
  }

  // ================================================================
  // SCREEN 5 — CLASSROOM
  // ================================================================
  const stageEl        = document.getElementById('stage');
  const captionEl      = document.getElementById('caption');
  const captionTextEl  = document.getElementById('caption-text');
  const lessonProgEl   = document.getElementById('lesson-progress');
  const sceneListEl    = document.getElementById('scene-list');
  const citationsEl    = document.getElementById('citations');
  const keyTermEl      = document.getElementById('key-term');
  const btnPlay        = document.getElementById('btn-play');
  const btnPrev        = document.getElementById('btn-prev');
  const btnNextScene   = document.getElementById('btn-next');
  const btnCaptions    = document.getElementById('btn-captions');
  const btnMute        = document.getElementById('btn-mute');
  const speedSelectEl  = document.getElementById('speed');
  const btnReteach     = document.getElementById('btn-reteach');
  const btnAssessment  = document.getElementById('btn-take-assessment');

  function renderClassroom() {
    const lesson = state.lesson;
    if (!lesson || !lesson.scenes || !lesson.scenes.length) { notify('No lesson scenes returned.'); return; }
    state.currentSceneIdx = 0;
    state.isPlaying = false;
    if (btnPlay) { btnPlay.textContent = 'Play ▶'; btnPlay.classList.remove('active'); }

    // Scene thumbnails
    if (sceneListEl) {
      sceneListEl.innerHTML = lesson.scenes.map((sc, i) => `
        <div class="scene-thumb ${i===0?'active':''}" data-scene="${i}">
          <div class="scene-preview-box">SCN ${String(i+1).padStart(2,'0')}</div>
          <div class="scene-thumb-title">${i+1}. ${esc(sc.title)}</div>
        </div>`).join('');
      sceneListEl.querySelectorAll('.scene-thumb').forEach(el => {
        el.addEventListener('click', () => showScene(parseInt(el.getAttribute('data-scene'))));
      });
    }

    // Citations
    if (citationsEl) {
      const allCitations = lesson.scenes.flatMap(sc => sc.citations || []);
      const unique = [...new Set(allCitations)];
      citationsEl.innerHTML = unique.length
        ? unique.slice(0,6).map(cid => `
            <div class="citation-chip" data-chunk="${cid}">
              <span>CHUNK #${cid}</span>
              <span style="color:var(--text-muted);">(Db2 Verified)</span>
            </div>`).join('')
        : '<div style="color:var(--text-dim);font-size:12px;">No citations yet.</div>';
      citationsEl.querySelectorAll('.citation-chip').forEach(chip => {
        chip.addEventListener('click', () => notify(`Db2 ground truth verified for chunk #${chip.getAttribute('data-chunk')}`, true));
      });
    }

    showScene(0);
  }

  function showScene(idx) {
    const lesson = state.lesson;
    if (!lesson || !lesson.scenes || idx < 0 || idx >= lesson.scenes.length) return;
    state.currentSceneIdx = idx;
    const sc    = lesson.scenes[idx];
    const total = lesson.scenes.length;

    if (lessonProgEl) lessonProgEl.style.width = `${((idx+1)/total)*100}%`;

    // Thumbnails
    if (sceneListEl) {
      sceneListEl.querySelectorAll('.scene-thumb').forEach(el => {
        el.classList.toggle('active', parseInt(el.getAttribute('data-scene')) === idx);
      });
    }

    // Caption bar — scenes use 'narration' field (confirmed from API)
    const narration = sc.narration || sc.narrative || '';
    if (captionTextEl) captionTextEl.textContent = narration ? `"${narration}"` : sc.title;

    // Key Term
    if (keyTermEl) {
      const kt = sc.key_term || lesson.scenes[0].key_term || '';
      if (!kt) {
        keyTermEl.innerHTML = '';
      } else if (kt.includes(':')) {
        const parts = kt.split(':');
        keyTermEl.innerHTML = `<div class="key-term-name"><span>KEY TERM: ${esc(parts[0].trim())}</span></div>
           <p class="key-term-def">${esc(parts.slice(1).join(':').trim())}</p>`;
      } else {
        keyTermEl.innerHTML = `<div class="key-term-name"><span>KEY TERM: ${esc(kt)}</span></div>
           <p class="key-term-def">Highlighted concept for Scene ${idx + 1}: ${esc(sc.title)}.</p>`;
      }
    }

    // Render Stage
    if (stageEl) {
      state.format === 'board' ? renderBoard(sc, idx, total) : renderVideoStage(sc, idx, total);
    }

    // Speech
    if (state.isPlaying && !state.isMuted && narration) speak(narration);
  }

  function renderVisualHtml(sc) {
    const v = sc.visual || {};
    const type = v.type || 'bullets';
    const bullets = Array.isArray(sc.bullets) ? sc.bullets : [];

    if (type === 'compare' && v.left && v.right) {
      return `
        <div class="vis-compare">
          <div class="vis-col">
            <div class="vis-col-title">${esc(v.left.title || 'Perspective A')}</div>
            <ul>${(v.left.points || []).map(p => `<li>${esc(p)}</li>`).join('')}</ul>
          </div>
          <div class="vis-col">
            <div class="vis-col-title">${esc(v.right.title || 'Perspective B')}</div>
            <ul>${(v.right.points || []).map(p => `<li>${esc(p)}</li>`).join('')}</ul>
          </div>
        </div>`;
    }
    if ((type === 'flow' || type === 'cycle') && Array.isArray(v.steps) && v.steps.length) {
      return `
        <div class="vis-flow">
          ${v.steps.map((s, i) => `
            ${i > 0 ? '<span class="vis-flow-arrow">→</span>' : ''}
            <div class="vis-flow-step">${esc(s)}</div>
          `).join('')}
          ${type === 'cycle' ? '<span class="vis-flow-arrow">↺</span>' : ''}
        </div>`;
    }
    if (type === 'timeline' && Array.isArray(v.events) && v.events.length) {
      return `
        <div class="vis-timeline">
          ${v.events.map(ev => `
            <div class="vis-ev">
              <span class="vis-ev-label">${esc(ev.label)}</span>
              <span>${esc(ev.detail)}</span>
            </div>`).join('')}
        </div>`;
    }
    if (type === 'equation' && v.latex) {
      return `
        <div class="vis-eq">
          <div class="vis-eq-code">${esc(v.latex)}</div>
          ${v.explanation ? `<p style="font-size:12.5px;color:var(--text-muted);margin:0;">${esc(v.explanation)}</p>` : ''}
        </div>`;
    }
    if (type === 'hierarchy' && v.root) {
      const children = Array.isArray(v.root.children) ? v.root.children : [];
      return `
        <div class="vis-eq" style="text-align:left;">
          <div style="font-weight:700;margin-bottom:10px;color:var(--text);">▸ ${esc(v.root.label)}</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;padding-left:14px;">
            ${children.map(ch => `<div class="vis-flow-step" style="font-weight:500;">${esc(ch.label || ch)}</div>`).join('')}
          </div>
        </div>`;
    }
    if (type === 'concept_map' && Array.isArray(v.nodes) && v.nodes.length) {
      const edges = Array.isArray(v.edges) ? v.edges : [];
      return `
        <div class="vis-eq" style="text-align:left;">
          <div class="vis-flow" style="margin-bottom:10px;">
            ${v.nodes.slice(0, 6).map(n => `<div class="vis-flow-step">${esc(n)}</div>`).join('')}
          </div>
          ${edges.length ? `<div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--text-muted);text-align:center;">
            ${edges.slice(0, 4).map(e => `${esc(e.from)} → ${esc(e.to)}`).join(' &nbsp;|&nbsp; ')}
          </div>` : ''}
        </div>`;
    }
    if (bullets.length) {
      return `
        <div class="vis-col">
          <div class="vis-col-title">${esc(sc.title)}</div>
          <ul class="vis-bullets">${bullets.map(b => `<li>${esc(b)}</li>`).join('')}</ul>
        </div>`;
    }
    return '';
  }

  function renderBoard(sc, idx, total) {
    const bullets  = Array.isArray(sc.bullets) ? sc.bullets : [];
    const narration = sc.narration || sc.narrative || '';
    const citations = (sc.citations || []).map(c => `#${c}`).join(', ') || 'Db2';

    const sqlMatch = narration.match(/```(?:sql)?\n?([\s\S]*?)```/i);
    const codeBlock = sqlMatch
      ? `<div class="board-code">${esc(sqlMatch[1])}</div>`
      : '';

    const visHtml = (sc.visual && sc.visual.type && sc.visual.type !== 'bullets')
      ? `<div class="board-visual">${renderVisualHtml(sc)}</div>`
      : '';

    stageEl.innerHTML = `
      <div class="stage-board">
        <div class="board-header">
          <span class="board-step-pill">STEP ${idx+1} OF ${total}</span>
          <span class="board-title">${esc(sc.title)}</span>
          <span class="board-chunk-badge">Source: ${citations}</span>
        </div>
        <div class="board-narrative">
          ${narration ? narration.split('\n').filter(l=>l.trim()).map(l=>`<p>${esc(l)}</p>`).join('') : ''}
          ${bullets.length ? `<ul style="margin-top:12px;padding-left:20px;">${bullets.map(b=>`<li style="margin-bottom:6px;">${esc(b)}</li>`).join('')}</ul>` : ''}
        </div>
        ${codeBlock}
        ${visHtml}
      </div>`;
  }

  function renderVideoStage(sc, idx, total) {
    const citations = (sc.citations || []).map(c => `#${c}`).join(', ') || '';
    stageEl.innerHTML = `
      <div style="width:100%;height:100%;position:relative;overflow:hidden;background:var(--stage-bg);">
        <div style="position:absolute;top:14px;left:18px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted);font-weight:600;">
          SCENE ${String(idx+1).padStart(2,'0')} / ${String(total).padStart(2,'0')} — ${esc(sc.title)}
        </div>
        ${citations ? `<div style="position:absolute;top:14px;right:18px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--emerald);font-weight:600;">
          CHUNKS: ${citations}
        </div>` : ''}
        <div class="vis-stage-wrap">
          ${renderVisualHtml(sc)}
        </div>
      </div>`;
  }

  // Speech
  function speak(text) {
    if (!('speechSynthesis' in window) || state.isMuted) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.replace(/[*#`_]/g,''));
    u.rate  = state.speechRate;
    u.onend = () => {
      if (state.isPlaying && state.lesson && state.currentSceneIdx < state.lesson.scenes.length - 1) {
        setTimeout(() => { if (state.isPlaying) showScene(state.currentSceneIdx + 1); }, 1000);
      }
    };
    window.speechSynthesis.speak(u);
  }

  if (btnPlay) btnPlay.addEventListener('click', () => {
    state.isPlaying = !state.isPlaying;
    btnPlay.textContent = state.isPlaying ? 'Pause ||' : 'Play ▶';
    btnPlay.classList.toggle('active', state.isPlaying);
    if (state.isPlaying && state.lesson) {
      speak((state.lesson.scenes[state.currentSceneIdx].narration || ''));
    } else if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  });

  if (btnNextScene) btnNextScene.addEventListener('click', () => {
    if (!state.lesson) return;
    showScene((state.currentSceneIdx + 1) % state.lesson.scenes.length);
  });
  if (btnPrev) btnPrev.addEventListener('click', () => {
    if (!state.lesson) return;
    showScene((state.currentSceneIdx - 1 + state.lesson.scenes.length) % state.lesson.scenes.length);
  });
  if (speedSelectEl) speedSelectEl.addEventListener('change', () => {
    state.speechRate = parseFloat(speedSelectEl.value) || 1.0;
  });
  if (btnCaptions) btnCaptions.addEventListener('click', function() {
    this.classList.toggle('active');
    if (captionEl) captionEl.style.display = this.classList.contains('active') ? 'flex' : 'none';
  });
  if (btnMute) btnMute.addEventListener('click', function() {
    state.isMuted = !state.isMuted;
    this.classList.toggle('active', state.isMuted);
    if (state.isMuted && 'speechSynthesis' in window) window.speechSynthesis.cancel();
  });

  const timelineScrubEl = document.getElementById('timeline-scrub');
  if (timelineScrubEl) timelineScrubEl.addEventListener('click', (e) => {
    if (!state.lesson || !state.lesson.scenes || !state.lesson.scenes.length) return;
    const rect = timelineScrubEl.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(0.999, (e.clientX - rect.left) / Math.max(rect.width, 1)));
    const targetIdx = Math.floor(ratio * state.lesson.scenes.length);
    showScene(targetIdx);
  });

  if (btnReteach) {
    btnReteach.addEventListener('click', async () => {
      const styles = ['step-by-step', 'worked example', 'analogy', 'overview'];
      const curPos = styles.indexOf(state.currentStyle);
      state.currentStyle = styles[(curPos + 1) % styles.length];
      btnReteach.disabled = true; btnReteach.querySelector('span') && (btnReteach.querySelector('span').textContent = 'Regenerating…');
      try {
        const data = await api('/api/lesson', 'POST', {
          student_id: state.student_id, concept_id: state.concept_id,
          format: state.format, style: state.currentStyle, loop_count: state.remediationLoop
        });
        state.lesson = data; renderClassroom();
        notify(`Teaching style switched to: ${state.currentStyle}`, true);
      } catch(e) { notify('Reteach error: ' + e.message); }
      finally {
        btnReteach.disabled = false;
        if (btnReteach.querySelector('span')) btnReteach.querySelector('span').textContent = `Explain differently (${state.currentStyle})`;
      }
    });
  }

  if (btnAssessment) {
    btnAssessment.addEventListener('click', () => {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      state.isPlaying = false;
      if (btnPlay) { btnPlay.textContent = 'Play ▶'; btnPlay.classList.remove('active'); }
      goTo(6); loadQuiz();
    });
  }

  // ================================================================
  // SCREEN 6 — ASSESSMENT
  // ================================================================
  const qCounterEl    = document.getElementById('q-counter');
  const qTextEl       = document.getElementById('q-text');
  const optContainerEl = document.getElementById('options-container');
  const btnSubmit     = document.getElementById('btn-submit-answer');
  const feedbackBoxEl = document.getElementById('feedback-box');

  async function loadQuiz() {
    if (!state.concept_id) { notify('No concept loaded.'); return; }
    if (qTextEl) qTextEl.textContent = 'Generating assessment questions from Db2 chunks…';
    if (optContainerEl) optContainerEl.innerHTML = '';
    if (feedbackBoxEl) feedbackBoxEl.classList.remove('show');
    if (btnSubmit) { btnSubmit.textContent = 'Submit Answer'; btnSubmit.className = 'btn btn-primary'; }
    try {
      const data = await api('/api/quiz/generate', 'POST', {
        concept_id: state.concept_id,
        student_id: state.student_id,
        loop_index: state.remediationLoop
      });
      if (data.used_fallback) {
        notify(`Quiz generated via offline fallback: ${data.fallback_reason || 'Live AI unavailable.'}`);
      }
      state.quizQuestions      = data.questions || [];
      state.currentQuestionIdx = 0;
      state.userAnswers        = [];
      state.hasSubmittedCurrent = false;
      renderQuestion();
    } catch (e) {
      notify('Quiz error: ' + e.message);
      if (qTextEl) qTextEl.textContent = 'Failed to load questions: ' + e.message;
    }
  }

  function renderQuestion() {
    const q = state.quizQuestions[state.currentQuestionIdx];
    if (!q) return;
    state.hasSubmittedCurrent = false;
    state._selectedOpt = null;

    if (qCounterEl) qCounterEl.textContent = `Question ${state.currentQuestionIdx+1} of ${state.quizQuestions.length}`;
    // API uses 'question_text', not 'text'
    if (qTextEl)    qTextEl.textContent = q.question_text || q.text || '';
    if (feedbackBoxEl) feedbackBoxEl.classList.remove('show');

    if (optContainerEl) {
      // API uses option_a/b/c/d
      const opts = {
        A: q.option_a || (q.options && q.options.A) || '',
        B: q.option_b || (q.options && q.options.B) || '',
        C: q.option_c || (q.options && q.options.C) || '',
        D: q.option_d || (q.options && q.options.D) || ''
      };
      optContainerEl.innerHTML = Object.entries(opts).map(([letter, text]) => `
        <div class="option-card" data-opt="${letter}">
          <span class="option-letter">${letter}</span>
          <span class="option-content">${esc(text)}</span>
        </div>`).join('');
      optContainerEl.querySelectorAll('.option-card').forEach(card => {
        card.addEventListener('click', () => {
          if (state.hasSubmittedCurrent) return;
          optContainerEl.querySelectorAll('.option-card').forEach(c => c.classList.remove('selected'));
          card.classList.add('selected');
          state._selectedOpt = card.getAttribute('data-opt');
        });
      });
    }

    if (btnSubmit) { btnSubmit.textContent = 'Submit Answer'; btnSubmit.className = 'btn btn-primary'; }
  }

  if (btnSubmit) {
    btnSubmit.addEventListener('click', async () => {
      const idx = state.currentQuestionIdx;
      const q   = state.quizQuestions[idx];

      if (!state.hasSubmittedCurrent) {
        if (!state._selectedOpt) { notify('Select an option first.'); return; }
        btnSubmit.textContent = 'Evaluating…'; btnSubmit.disabled = true;
        try {
          const r = await api('/api/quiz/answer', 'POST', {
            student_id: state.student_id,
            concept_id: state.concept_id,
            answers: [{ question_id: q.question_id, selected_letter: state._selectedOpt }]
          });
          const result = (r.results && r.results[0]) ? r.results[0] : {};
          state.userAnswers.push(result);
          state.hasSubmittedCurrent = true;

          // Show feedback
          if (feedbackBoxEl) {
            const ok = result.is_correct;
            feedbackBoxEl.innerHTML = `
              <div class="feedback-header">
                <span class="badge ${ok ? 'badge-success' : 'badge-danger'}">${ok ? '✓ Correct' : `✗ Incorrect — Correct: ${result.correct_letter}`}</span>
                <span style="font-size:11px;font-family:'JetBrains Mono',monospace;color:var(--text-muted);">
                  Chunk #${result.citation_chunk_id || q.source_chunk_id || '—'}
                </span>
              </div>
              <p class="feedback-explanation">${esc(result.explanation || '')}</p>`;
            feedbackBoxEl.classList.toggle('incorrect', !ok);
            feedbackBoxEl.classList.add('show');
          }

          // Mark selected card right/wrong
          if (optContainerEl) {
            optContainerEl.querySelectorAll('.option-card').forEach(c => {
              if (c.getAttribute('data-opt') === state._selectedOpt)
                c.style.borderColor = result.is_correct ? 'var(--emerald)' : 'var(--rose)';
              if (c.getAttribute('data-opt') === result.correct_letter && !result.is_correct)
                c.style.borderColor = 'var(--emerald)';
            });
          }

          if (idx < state.quizQuestions.length - 1) {
            btnSubmit.textContent = 'Next Question →'; btnSubmit.className = 'btn btn-secondary';
          } else {
            btnSubmit.textContent = 'Evaluate Mastery Gate →'; btnSubmit.className = 'btn btn-success';
          }
        } catch (e) {
          notify('Answer error: ' + e.message);
          btnSubmit.textContent = 'Submit Answer';
        } finally { btnSubmit.disabled = false; }

      } else {
        if (idx < state.quizQuestions.length - 1) {
          state.currentQuestionIdx++;
          renderQuestion();
        } else {
          goTo(7); evalGate();
        }
      }
    });
  }

  // ================================================================
  // SCREEN 7 — MASTERY GATE
  // ================================================================
  const gateCircleEl  = document.getElementById('gate-score-circle');
  const gatePctEl     = document.getElementById('gate-pct-label');
  const crit1El       = document.getElementById('crit-1');
  const crit2El       = document.getElementById('crit-2');
  const crit3El       = document.getElementById('crit-3');
  const stateNotYet   = document.getElementById('state-not-yet');
  const statePassed   = document.getElementById('state-passed');
  const stateHumanEl  = document.getElementById('state-human-help');
  const btnReteachLoop = document.getElementById('btn-reteach-loop');
  const btnNextTopic  = document.getElementById('btn-next-topic');

  async function evalGate() {
    try {
      const r = await api('/api/gate', 'POST', {
        student_id: state.student_id,
        concept_id: state.concept_id,
        loop_count: state.remediationLoop
      });
      state.gateResult  = r;
      state.lastEventId = r.event_id;

      const pct = Math.round((r.mastery_score || 0) * 100);
      if (gatePctEl) gatePctEl.textContent = `${pct}%`;
      if (gateCircleEl) {
        const c = 2 * Math.PI * 50;
        gateCircleEl.style.strokeDasharray  = c;
        gateCircleEl.style.strokeDashoffset = c - c * (r.mastery_score || 0);
        gateCircleEl.style.stroke = r.gate_passed ? 'var(--emerald)' : pct >= 50 ? 'var(--amber)' : 'var(--rose)';
      }

      function setCrit(el, met, text) {
        if (!el) return;
        el.className = 'criteria-item' + (met ? ' met' : '');
        const icon = el.querySelector('.criteria-icon');
        const span = el.querySelector('span:last-child');
        if (icon) icon.textContent = met ? '✓' : '×';
        if (span) span.textContent = text;
      }
      setCrit(crit1El, pct >= 80, `Mastery ≥ 80% (Current: ${pct}%)`);
      setCrit(crit2El, r.attempt_count >= 5, `Min 5 attempts (Done: ${r.attempt_count})`);
      setCrit(crit3El, r.distinct_difficulties >= 2, `Multi-difficulty ≥ 2 (Tested: ${r.distinct_difficulties})`);

      [stateNotYet, statePassed, stateHumanEl].forEach(s => s && s.classList.remove('active'));

      if (r.gate_passed) {
        if (statePassed) statePassed.classList.add('active');
        const passedTitle = document.getElementById('passed-concept-title');
        if (passedTitle) passedTitle.textContent = `${state.activeTopic || 'Curriculum Concept'} Mastered`;
        if (btnNextTopic) {
          btnNextTopic.textContent = r.next_concept ? `Next: ${r.next_concept.name} →` : 'Choose Next Topic →';
        }
        notify('Mastery gate passed! Concept unlocked in Db2.', true);
      } else if (r.needs_human_help) {
        if (stateHumanEl) stateHumanEl.classList.add('active');
        notify('3 remediation loops exhausted. Human help recommended.');
      } else {
        if (stateNotYet) {
          stateNotYet.classList.add('active');
          const loopBadge = document.getElementById('gate-loop-badge');
          const summaryEl = document.getElementById('gate-decision-summary');
          const styleHintEl = document.getElementById('gate-style-hint');
          const prereqChainEl = document.getElementById('prereq-chain');
          const rcName  = stateNotYet.querySelector('.root-cause-name');
          const rcScore = stateNotYet.querySelector('.root-cause-score');

          if (loopBadge) loopBadge.textContent = `Loop ${r.loop_count || 1} of 3`;
          if (summaryEl) summaryEl.textContent = r.reason || 'Gate threshold not yet reached.';
          if (styleHintEl) styleHintEl.textContent = `Switching teaching modality to: ${r.next_style || 'analogy'}`;

          if (r.root_cause) {
            if (rcName)  rcName.textContent  = `Root Cause Diagnosed: ${r.root_cause.name}`;
            if (rcScore) rcScore.textContent = `Mastery: ${Math.round((r.root_cause.mastery_score||0)*100)}%`;
          } else {
            if (rcName)  rcName.textContent  = `Review Needed: ${state.activeTopic || 'Current Topic'}`;
            if (rcScore) rcScore.textContent = `Mastery: ${pct}%`;
          }

          if (prereqChainEl) {
            const chain = Array.isArray(r.prereq_chain) ? r.prereq_chain : [];
            if (chain.length) {
              const rcId = r.root_cause ? r.root_cause.concept_id : null;
              prereqChainEl.style.display = 'flex';
              prereqChainEl.innerHTML = chain.map((node, i) => `
                ${i > 0 ? '<span class="prereq-arrow">→</span>' : ''}
                <div class="prereq-node ${node.concept_id === rcId ? 'failed' : ''}">
                  ${esc(node.name)} (${Math.round((node.mastery_score||0)*100)}%)
                </div>`).join('') +
                `<span class="prereq-arrow">→</span><div class="prereq-node">${esc(state.activeTopic || 'Current')} (${pct}%)</div>`;
            } else {
              prereqChainEl.style.display = 'none';
              prereqChainEl.innerHTML = '';
            }
          }
        }
        if (btnReteachLoop) btnReteachLoop.textContent = `Remediation Loop ${(r.loop_count || 1)+1} of 3 (${r.next_style}) →`;
      }
    } catch (e) { notify('Gate error: ' + e.message); }
  }

  if (btnReteachLoop) {
    btnReteachLoop.addEventListener('click', async () => {
      state.remediationLoop++;
      if (state.gateResult) state.currentStyle = state.gateResult.next_style || state.currentStyle;
      goTo(5);
      try {
        const data = await api('/api/lesson', 'POST', {
          student_id: state.student_id, concept_id: state.concept_id,
          format: state.format, style: state.currentStyle, loop_count: state.remediationLoop
        });
        state.lesson = data; renderClassroom();
        notify(`Remediation loop ${state.remediationLoop} — style: ${state.currentStyle}`, true);
      } catch(e) { notify('Remediation lesson error: ' + e.message); }
    });
  }

  if (btnNextTopic) {
    btnNextTopic.addEventListener('click', () => {
      if (state.gateResult && state.gateResult.next_concept) {
        state.concept_id    = state.gateResult.next_concept.concept_id;
        state.remediationLoop = 1;
        setTopic(state.gateResult.next_concept.name);
        goTo(4);
      } else { goTo(2); }
    });
  }

  const btnConnectHuman = document.getElementById('btn-connect-human');
  if (btnConnectHuman) {
    btnConnectHuman.addEventListener('click', () => {
      goTo(8);
    });
  }

  // ================================================================
  // SCREEN 8 — LEDGER
  // ================================================================
  const tabChartEl    = document.getElementById('tab-ledger-chart');
  const tabWhyEl      = document.getElementById('tab-ledger-why');
  const panelChartEl  = document.getElementById('panel-ledger-chart');
  const panelWhyEl    = document.getElementById('panel-ledger-why');
  const progChartEl   = document.getElementById('progress-chart');
  const progMatrixEl  = document.getElementById('progress-matrix');
  const whySqlEl      = document.getElementById('why-sql');
  const whyTableEl    = document.getElementById('why-table');

  function switchLedgerTab(which) {
    [tabChartEl, tabWhyEl].forEach(t => t && t.classList.remove('active'));
    if (which === 'chart') { if (tabChartEl) tabChartEl.classList.add('active'); if (panelChartEl) panelChartEl.style.display='block'; if (panelWhyEl) panelWhyEl.style.display='none'; loadProgress(); }
    else                   { if (tabWhyEl) tabWhyEl.classList.add('active'); if (panelWhyEl) panelWhyEl.style.display='block'; if (panelChartEl) panelChartEl.style.display='none'; loadWhy(); }
  }
  if (tabChartEl) tabChartEl.addEventListener('click', () => switchLedgerTab('chart'));
  if (tabWhyEl)   tabWhyEl.addEventListener('click',   () => switchLedgerTab('why'));

  async function loadProgress() {
    if (!state.student_id || !progChartEl) return;
    try {
      const data = await api(`/api/progress/${state.student_id}`);
      if (data.latest_event_id && !state.lastEventId) {
        state.lastEventId = data.latest_event_id;
      }
      const history = data.history || [];
      const progress = data.progress || [];
      if (!history.length) {
        progChartEl.innerHTML = `<div style="padding:28px;text-align:center;color:var(--text-muted);">No attempts recorded yet. Complete a quiz to view mastery trajectory.</div>`;
      } else {
        const bars = history.slice(-10).map((h, i) => {
          const pct = Math.round(((h.score_after ?? h.mastery_score ?? 0)) * 100);
          return `<div class="chart-bar-group">
            <div class="chart-bar${pct>=80?' passed':''}" style="height:${Math.max(pct,4)}%;" data-score="${pct}%"></div>
            <span class="chart-label">#${i+1}</span>
          </div>`;
        }).join('');
        progChartEl.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="font-size:12.5px;font-weight:600;color:var(--text);">Mastery Trajectory (%)</span>
            <span style="font-size:11px;color:var(--text-muted);font-family:'JetBrains Mono',monospace;">Threshold: 80%</span>
          </div>
          <div class="chart-bars-wrap">${bars}</div>`;
      }
      if (progMatrixEl) {
        progMatrixEl.innerHTML = progress.length ? `
          <div class="table-responsive" style="margin-top:16px;">
            <table class="data-table">
              <thead>
                <tr><th>Concept</th><th>Mastery</th><th>Attempts</th><th>Difficulty Span</th><th>Status</th></tr>
              </thead>
              <tbody>
                ${progress.map(p => `
                  <tr>
                    <td style="font-weight:600;">${esc(p.concept_name)}</td>
                    <td style="font-family:'JetBrains Mono',monospace;">${Math.round((p.current_mastery||0)*100)}%</td>
                    <td style="font-family:'JetBrains Mono',monospace;">${p.total_attempts || 0}</td>
                    <td style="font-family:'JetBrains Mono',monospace;">${p.distinct_difficulties || 0}</td>
                    <td><span class="badge ${p.is_mastered ? 'badge-success' : 'badge-db2'}">${p.is_mastered ? 'Mastered' : 'In Progress'}</span></td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>` : '';
      }
    } catch(e) { if (progChartEl) progChartEl.innerHTML = `<div style="color:var(--rose);padding:16px;">${esc(e.message)}</div>`; }
  }

  async function loadWhy() {
    const defaultSql = `WITH prereq_tree (concept_id, prereq_id, depth) AS (
    SELECT cp.concept_id, cp.prereq_id, 1
    FROM concept_prereqs cp
    WHERE cp.concept_id = ?
    UNION ALL
    SELECT pt.concept_id, cp2.prereq_id, pt.depth + 1
    FROM prereq_tree pt, concept_prereqs cp2
    WHERE pt.prereq_id = cp2.concept_id
)
SELECT c.concept_id, c.name, COALESCE(m.mastery_score, 0.0) AS mastery_score, MIN(pt.depth) AS min_depth
FROM prereq_tree pt
JOIN concepts c ON pt.prereq_id = c.concept_id
LEFT JOIN mastery m ON m.student_id = ? AND m.concept_id = c.concept_id
GROUP BY c.concept_id, c.name, m.mastery_score
ORDER BY mastery_score ASC, min_depth DESC;`;
    if (!state.lastEventId) {
      if (whySqlEl) whySqlEl.textContent = `-- Complete a mastery gate check first to inspect its live Db2 event.\n\n${defaultSql}`;
      if (whyTableEl) {
        const tbody = whyTableEl.querySelector('tbody');
        if (tbody) tbody.innerHTML = '';
      }
      return;
    }
    try {
      const data = await api(`/api/why/${state.lastEventId}`);
      if (whySqlEl) whySqlEl.textContent = data.sql_query || defaultSql;
      if (whyTableEl) {
        const tbody = whyTableEl.querySelector('tbody') || whyTableEl;
        const rows = Array.isArray(data.prereq_rows) ? data.prereq_rows : [];
        tbody.innerHTML = rows.length ? rows.map(r => `
          <tr>
            <td style="font-family:'JetBrains Mono',monospace;">ID_${r.concept_id}</td>
            <td style="font-weight:600;">${esc(r.name)}</td>
            <td style="font-family:'JetBrains Mono',monospace;">${Math.round((r.mastery_score||0)*100)}%</td>
            <td style="font-family:'JetBrains Mono',monospace;">depth ${r.min_depth ?? r.depth ?? 1}</td>
          </tr>`).join('')
          : `<tr><td colspan="4" style="color:var(--text-muted);text-align:center;">No prerequisite gaps linked for this event (${esc(data.reason || data.event_type)}).</td></tr>`;
      }
    } catch(e) { if (whySqlEl) whySqlEl.textContent = '-- ' + e.message; }
  }

  // ================================================================
  // BOOT
  // ================================================================
  init();

})();
