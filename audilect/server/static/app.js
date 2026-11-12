// Audilect High-Density Technical Web Cockpit Logic

let currentSession = null;
let currentSlideId = null;
let currentSegId = null;
let activeJobId = null;
let jobPollTimer = null;
let activeElaborationFilter = "all";

const video = document.getElementById("lecture-video");
const videoSource = document.getElementById("video-source");
const timeDisplay = document.getElementById("time-display");
const slidesDeck = document.getElementById("slides-deck");
const transcriptStream = document.getElementById("transcript-stream");
const checkpointsList = document.getElementById("checkpoints-list");
const primersList = document.getElementById("primers-list");
const ankiPreview = document.getElementById("anki-preview");
const cornellPreview = document.getElementById("cornell-preview");

// Format seconds into MM:SS
function formatTime(sec) {
  if (isNaN(sec) || sec < 0) return "00:00";
  const s = Math.floor(sec);
  const m = Math.floor(s / 60);
  const remSec = s % 60;
  return `${String(m).padStart(2, '0')}:${String(remSec).padStart(2, '0')}`;
}

// Initialize and fetch sessions
async function init() {
  setupEventListeners();
  await loadAIConfig();
  const sessions = await fetchSessions();
  if (sessions.length > 0) {
    loadSession(sessions[0].session_id);
  }
}


// Set up UI event listeners
function setupEventListeners() {
  // Video time updates
  video.addEventListener("timeupdate", onVideoTimeUpdate);

  // Playback rate buttons
  document.querySelectorAll(".playback-rate-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".playback-rate-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      video.playbackRate = parseFloat(btn.dataset.rate);
    });
  });

  // Tab switching (Recall / Concepts / Exports)
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const tabId = `tab-${btn.dataset.tab}`;
      const content = document.getElementById(tabId);
      if (content) content.classList.add("active");
    });
  });

  // Elaboration Filter Chips (ALL, CLAIMS, CONCEPTS, EVIDENCE, CONTRASTS)
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeElaborationFilter = chip.dataset.filter || "all";
      applyTranscriptFilters();
    });
  });

  // Transcript search filter
  const searchInput = document.getElementById("transcript-search");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      applyTranscriptFilters();
    });
  }

  // File Ingest modal controls
  const btnIngest = document.getElementById("btn-ingest-modal");
  if (btnIngest) {
    btnIngest.addEventListener("click", () => {
      document.getElementById("process-modal").style.display = "flex";
    });
  }

  const btnOpenSessions = document.getElementById("btn-open-sessions");
  if (btnOpenSessions) {
    btnOpenSessions.addEventListener("click", openSessionsModal);
  }

  // Direct Screen / Tab Recording (Share Tab for Zoom / Meet / YouTube / Browser)
  const btnOpenRecord = document.getElementById("btn-open-record");
  if (btnOpenRecord) {
    btnOpenRecord.addEventListener("click", () => {
      startScreenRecording();
    });
  }

  // Stop recording buttons
  const btnStageStop = document.getElementById("btn-stage-stop-record");
  if (btnStageStop) {
    btnStageStop.addEventListener("click", stopScreenRecording);
  }
  const btnTopStop = document.getElementById("btn-top-stop-record");
  if (btnTopStop) {
    btnTopStop.addEventListener("click", stopScreenRecording);
  }

  // Modal close buttons (X)
  const btnXProcess = document.getElementById("btn-x-process");
  if (btnXProcess) {
    btnXProcess.addEventListener("click", () => {
      document.getElementById("process-modal").style.display = "none";
    });
  }
  const btnXSessions = document.getElementById("btn-x-sessions");
  if (btnXSessions) {
    btnXSessions.addEventListener("click", () => {
      document.getElementById("sessions-modal").style.display = "none";
    });
  }

  // Modal Cancel / Close buttons
  const btnCancelModal = document.getElementById("btn-cancel-modal");
  if (btnCancelModal) {
    btnCancelModal.addEventListener("click", () => {
      document.getElementById("process-modal").style.display = "none";
    });
  }
  const btnCloseSessions = document.getElementById("btn-close-sessions");
  if (btnCloseSessions) {
    btnCloseSessions.addEventListener("click", () => {
      document.getElementById("sessions-modal").style.display = "none";
    });
  }

  // AI Config modal controls
  const btnOpenAI = document.getElementById("btn-open-ai-modal");
  if (btnOpenAI) {
    btnOpenAI.addEventListener("click", () => {
      renderAIModalFields();
      document.getElementById("ai-modal").style.display = "flex";
    });
  }
  const btnXAI = document.getElementById("btn-x-ai");
  if (btnXAI) {
    btnXAI.addEventListener("click", () => {
      document.getElementById("ai-modal").style.display = "none";
    });
  }
  const btnCancelAI = document.getElementById("btn-cancel-ai");
  if (btnCancelAI) {
    btnCancelAI.addEventListener("click", () => {
      document.getElementById("ai-modal").style.display = "none";
    });
  }

  // Segmented Provider switch (Gemini vs Groq)
  const btnSelGemini = document.getElementById("btn-select-gemini");
  if (btnSelGemini) {
    btnSelGemini.addEventListener("click", () => {
      selectedAIProvider = "gemini";
      renderAIModalFields();
    });
  }
  const btnSelGroq = document.getElementById("btn-select-groq");
  if (btnSelGroq) {
    btnSelGroq.addEventListener("click", () => {
      selectedAIProvider = "groq";
      renderAIModalFields();
    });
  }

  // Toggle API key mask visibility
  const btnToggleMask = document.getElementById("btn-toggle-key-mask");
  if (btnToggleMask) {
    btnToggleMask.addEventListener("click", () => {
      const input = document.getElementById("ai-api-key-input");
      if (input.type === "password") {
        input.type = "text";
        btnToggleMask.innerText = "HIDE";
      } else {
        input.type = "password";
        btnToggleMask.innerText = "SHOW";
      }
    });
  }

  // Test Connection
  const btnTestAI = document.getElementById("btn-test-ai-key");
  if (btnTestAI) {
    btnTestAI.addEventListener("click", testAIConnection);
  }

  // Save Configuration
  const btnSaveAI = document.getElementById("btn-save-ai");
  if (btnSaveAI) {
    btnSaveAI.addEventListener("click", saveAIConfiguration);
  }

  // Reprocess modal controls
  const btnReprocess = document.getElementById("btn-reprocess");
  if (btnReprocess) {
    btnReprocess.addEventListener("click", () => {
      if (!currentSession) {
        alert("Please load a lecture session first.");
        return;
      }
      openReprocessModalFor(currentSession.session_id, currentSession.video_title);
    });
  }
  const btnXReprocess = document.getElementById("btn-x-reprocess");
  if (btnXReprocess) {
    btnXReprocess.addEventListener("click", () => {
      document.getElementById("reprocess-modal").style.display = "none";
    });
  }
  const btnCancelReprocess = document.getElementById("btn-cancel-reprocess");
  if (btnCancelReprocess) {
    btnCancelReprocess.addEventListener("click", () => {
      document.getElementById("reprocess-modal").style.display = "none";
    });
  }

  const btnReprocessAI = document.getElementById("btn-reprocess-ai");
  if (btnReprocessAI) {
    btnReprocessAI.addEventListener("click", () => {
      const modal = document.getElementById("reprocess-modal");
      const sid = modal.dataset.sessionId || (currentSession ? currentSession.session_id : null);
      if (sid) triggerReprocess("ai", sid);
    });
  }

  const btnReprocessFull = document.getElementById("btn-reprocess-full");
  if (btnReprocessFull) {
    btnReprocessFull.addEventListener("click", () => {
      const modal = document.getElementById("reprocess-modal");
      const sid = modal.dataset.sessionId || (currentSession ? currentSession.session_id : null);
      if (sid) triggerReprocess("full", sid);
    });
  }

  // Backdrop click on modal overlays to close
  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.style.display = "none";
      }
    });
  });

  // Global Escape key handler
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay").forEach(m => m.style.display = "none");
    }
  });

  // Sidebar Panel Toggles (Slide bookmarks & Notes panels)
  const cockpitGrid = document.getElementById("cockpit-grid");
  const toggleLeftBtn = document.getElementById("btn-toggle-left");
  const toggleRightBtn = document.getElementById("btn-toggle-right");
  const closeLeftBtn = document.getElementById("btn-close-left-panel");
  const closeRightBtn = document.getElementById("btn-close-right-panel");

  function toggleLeftPanel() {
    cockpitGrid.classList.toggle("left-collapsed");
    const isCollapsed = cockpitGrid.classList.contains("left-collapsed");
    if (toggleLeftBtn) toggleLeftBtn.style.opacity = isCollapsed ? "0.6" : "1.0";
  }

  function toggleRightPanel() {
    cockpitGrid.classList.toggle("right-collapsed");
    const isCollapsed = cockpitGrid.classList.contains("right-collapsed");
    if (toggleRightBtn) toggleRightBtn.style.opacity = isCollapsed ? "0.6" : "1.0";
  }

  if (toggleLeftBtn) toggleLeftBtn.addEventListener("click", toggleLeftPanel);
  if (closeLeftBtn) closeLeftBtn.addEventListener("click", toggleLeftPanel);
  if (toggleRightBtn) toggleRightBtn.addEventListener("click", toggleRightPanel);
  if (closeRightBtn) closeRightBtn.addEventListener("click", toggleRightPanel);

  // Theme toggle (Default is crisp Light Mode)
  const toggleThemeBtn = document.getElementById("btn-toggle-theme");
  const themeIconEl = document.getElementById("theme-icon-container");
  const themeLabelEl = document.getElementById("theme-btn-label");

  function updateThemeButton(isDark) {
    if (isDark) {
      document.body.classList.add("theme-dark");
      if (themeIconEl) {
        themeIconEl.innerHTML = `<svg class="icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`;
      }
      if (themeLabelEl) themeLabelEl.innerText = "Light";
      if (toggleThemeBtn) toggleThemeBtn.title = "Switch to Light Mode";
    } else {
      document.body.classList.remove("theme-dark");
      if (themeIconEl) {
        themeIconEl.innerHTML = `<svg class="icon-svg" viewBox="0 0 24 24"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;
      }
      if (themeLabelEl) themeLabelEl.innerText = "Dark";
      if (toggleThemeBtn) toggleThemeBtn.title = "Switch to Dark Mode";
    }
  }

  const savedTheme = localStorage.getItem("audilect-theme") || "light";
  updateThemeButton(savedTheme === "dark");

  if (toggleThemeBtn) {
    toggleThemeBtn.addEventListener("click", () => {
      const isCurrentlyDark = document.body.classList.contains("theme-dark");
      const nextThemeIsDark = !isCurrentlyDark;
      localStorage.setItem("audilect-theme", nextThemeIsDark ? "dark" : "light");
      updateThemeButton(nextThemeIsDark);
    });
  }

  // Ingestion action
  const btnStartProcess = document.getElementById("btn-start-process");
  if (btnStartProcess) {
    btnStartProcess.addEventListener("click", startIngest);
  }

  // Download export buttons
  const btnPdf = document.getElementById("btn-download-pdf");
  if (btnPdf) {
    btnPdf.addEventListener("click", () => {
      if (!currentSession) {
        alert("Please load a lecture session first.");
        return;
      }
      window.location.href = `/api/export/pdf/${currentSession.session_id}`;
    });
  }

  const btnViewPdf = document.getElementById("btn-view-pdf");
  if (btnViewPdf) {
    btnViewPdf.addEventListener("click", () => {
      if (!currentSession) {
        alert("Please load a lecture session first.");
        return;
      }
      window.open(`/api/export/pdf/${currentSession.session_id}`, "_blank");
    });
  }

  const btnAnki = document.getElementById("btn-download-anki");
  if (btnAnki) {
    btnAnki.addEventListener("click", () => {
      if (!currentSession) return;
      window.location.href = `/api/export/anki/${currentSession.session_id}`;
    });
  }
  const btnCornell = document.getElementById("btn-download-cornell");
  if (btnCornell) {
    btnCornell.addEventListener("click", () => {
      if (!currentSession) return;
      window.location.href = `/api/export/cornell/${currentSession.session_id}`;
    });
  }
}

// AI ENGINE CLIENT LOGIC
let currentAIConfig = null;
let selectedAIProvider = "gemini";

const AI_MODELS = {
  gemini: [
    { id: "gemini-3.5-flash-lite", name: "gemini-3.5-flash-lite (Fastest, High Free Quota)" },
    { id: "gemini-3.5-flash", name: "gemini-3.5-flash (High Intelligence & Density)" },
    { id: "gemini-3-flash-preview", name: "gemini-3-flash-preview (Preview Release)" },
    { id: "gemini-2.5-flash-lite", name: "gemini-2.5-flash-lite" }
  ],
  groq: [
    { id: "llama-3.3-70b-versatile", name: "llama-3.3-70b-versatile (Flagship, 500+ tok/s)" },
    { id: "llama-3.1-8b-instant", name: "llama-3.1-8b-instant (Ultra-fast)" }
  ]
};

const AI_INFO = {
  gemini: {
    desc: "Google Gemini 1.5/2.0 Flash: Massive 1M-token context window handles full 2-hour lectures with zero truncation. Free tier: 15 RPM / 1,500 requests per day.",
    link: "https://aistudio.google.com/app/apikey"
  },
  groq: {
    desc: "Groq LPU Inference (Llama 3.3 70B): Instant 500+ tokens/sec throughput for rapid question drafting. Free tier with generous daily token allowance.",
    link: "https://console.groq.com/keys"
  }
};

async function loadAIConfig() {
  try {
    const res = await fetch("/api/config/ai");
    if (!res.ok) return;
    currentAIConfig = await res.json();
    selectedAIProvider = currentAIConfig.provider || "gemini";
    updateAIHeaderBadge();
  } catch (err) {
    console.error("Failed to load AI config:", err);
  }
}

function updateAIHeaderBadge() {
  const btn = document.getElementById("btn-open-ai-modal");
  if (!btn || !currentAIConfig) return;
  if (currentAIConfig.has_active_key) {
    btn.innerHTML = `AI: <span style="color: var(--accent-green); font-weight: 700;">${currentAIConfig.provider.toUpperCase()}</span>`;
  } else {
    btn.innerHTML = `AI: <span style="color: var(--accent-yellow)">FALLBACK NLU</span>`;
  }
}

function renderAIModalFields() {
  // Update provider toggle buttons
  const gemBtn = document.getElementById("btn-select-gemini");
  const groqBtn = document.getElementById("btn-select-groq");
  if (gemBtn) gemBtn.classList.toggle("active", selectedAIProvider === "gemini");
  if (groqBtn) groqBtn.classList.toggle("active", selectedAIProvider === "groq");

  // Update description and link
  const infoEl = document.getElementById("ai-provider-info");
  const linkEl = document.getElementById("ai-key-portal-link");
  if (infoEl) infoEl.innerText = AI_INFO[selectedAIProvider].desc;
  if (linkEl) linkEl.href = AI_INFO[selectedAIProvider].link;

  // Update model select
  const modelSelect = document.getElementById("ai-model-select");
  if (modelSelect) {
    const models = AI_MODELS[selectedAIProvider];
    modelSelect.innerHTML = models.map(m => `<option value="${m.id}">${m.name}</option>`).join("");
    const curModel = selectedAIProvider === "gemini" ? currentAIConfig?.gemini_model : currentAIConfig?.groq_model;
    if (curModel) modelSelect.value = curModel;
  }

  // Update key input placeholder
  const keyInput = document.getElementById("ai-api-key-input");
  const maskedKey = selectedAIProvider === "gemini" ? currentAIConfig?.gemini_key_masked : currentAIConfig?.groq_key_masked;
  if (keyInput) {
    keyInput.value = "";
    keyInput.placeholder = maskedKey ? `Configured: ${maskedKey} (Leave empty to keep)` : `Paste free ${selectedAIProvider.toUpperCase()} key...`;
  }

  // Update telemetry status box
  const telemetryEl = document.getElementById("ai-telemetry-text");
  if (telemetryEl) {
    if (currentAIConfig?.has_active_key) {
      telemetryEl.innerHTML = `<span style="color: var(--accent-green)">ACTIVE:</span> ${currentAIConfig.status_label}`;
    } else {
      telemetryEl.innerHTML = `<span style="color: var(--text-muted)">NO KEY SET - ACTIVE: DETERMINISTIC NLU FALLBACK</span>`;
    }
  }
}

async function testAIConnection() {
  const telemetryEl = document.getElementById("ai-telemetry-text");
  const keyInput = document.getElementById("ai-api-key-input");
  const modelSelect = document.getElementById("ai-model-select");
  const testBtn = document.getElementById("btn-test-ai-key");

  let apiKey = keyInput.value.trim();
  testBtn.disabled = true;
  telemetryEl.innerHTML = `Testing connection to ${selectedAIProvider.toUpperCase()}...`;

  try {
    const res = await fetch("/api/config/ai/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: selectedAIProvider,
        api_key: apiKey,
        model_name: modelSelect.value
      })
    });
    const result = await res.json();
    testBtn.disabled = false;

    if (result.success) {
      telemetryEl.innerHTML = `<span style="color: var(--accent-green)">[CONNECTED] ${result.message}</span>`;
    } else {
      telemetryEl.innerHTML = `<span style="color: var(--accent-red)">[ERROR] ${result.error}</span>`;
    }
  } catch (err) {
    testBtn.disabled = false;
    telemetryEl.innerHTML = `<span style="color: var(--accent-red)">[ERROR] Network error testing AI: ${err.message}</span>`;
  }
}

async function saveAIConfiguration() {
  const keyInput = document.getElementById("ai-api-key-input");
  const modelSelect = document.getElementById("ai-model-select");
  const saveBtn = document.getElementById("btn-save-ai");

  const apiKey = keyInput.value.trim();
  saveBtn.disabled = true;
  saveBtn.innerText = "SAVING...";

  try {
    const payload = {
      provider: selectedAIProvider,
      model_name: modelSelect.value
    };
    if (apiKey) {
      payload.api_key = apiKey;
    }

    const res = await fetch("/api/config/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Save failed");
    currentAIConfig = await res.json();

    saveBtn.innerText = "SAVED";
    updateAIHeaderBadge();
    renderAIModalFields();

    setTimeout(() => {
      saveBtn.disabled = false;
      saveBtn.innerText = "SAVE CONFIGURATION";
      document.getElementById("ai-modal").style.display = "none";
    }, 600);

  } catch (err) {
    saveBtn.disabled = false;
    saveBtn.innerText = "SAVE CONFIGURATION";
    alert("Failed to save AI configuration: " + err.message);
  }
}

// Filter transcript segments by search term and elaboration category
function applyTranscriptFilters() {
  const searchInput = document.getElementById("transcript-search");
  const query = searchInput ? searchInput.value.toLowerCase().trim() : "";

  document.querySelectorAll(".transcript-segment").forEach(seg => {
    const textEl = seg.querySelector(".spoken-lecture-text") || seg.querySelector(".seg-text");
    const calloutEl = seg.querySelector(".callout-content");
    const spokenText = textEl ? textEl.innerText.toLowerCase() : "";
    const calloutText = calloutEl ? calloutEl.innerText.toLowerCase() : "";
    const elabType = seg.dataset.elaborationType || "none";

    const matchesQuery = !query || spokenText.includes(query) || calloutText.includes(query);
    const matchesFilter = (activeElaborationFilter === "all") || (elabType === activeElaborationFilter);

    if (matchesQuery && matchesFilter) {
      seg.style.display = "flex";
    } else {
      seg.style.display = "none";
    }
  });
}


// Fetch list of sessions
async function fetchSessions() {
  try {
    const res = await fetch("/api/sessions");
    return await res.json();
  } catch (err) {
    console.error("Failed to fetch sessions", err);
    return [];
  }
}

// Load a session
async function loadSession(sessionId) {
  try {
    const res = await fetch(`/api/session/${sessionId}`);
    if (!res.ok) throw new Error("Session fetch failed");
    currentSession = await res.json();
    renderSession(currentSession);
  } catch (err) {
    console.error("Error loading session:", err);
  }
}

// Render full session UI
function renderSession(data) {
  // Update title and slide count
  const titleEl = document.getElementById("session-title-display");
  if (titleEl) titleEl.innerText = data.video_title;
  const slideCountBadge = document.getElementById("slide-count-badge");
  if (slideCountBadge) slideCountBadge.innerText = `${data.total_slides} SLIDES`;

  // Update video player
  video.srcObject = null;
  videoSource.src = `/api/video/${data.session_id}`;
  video.load();

  // Render Slides Deck
  renderSlidesDeck(data.slides, data.session_id);

  // Render Transcript with color-coded elaborations
  renderTranscript(data.segments);

  // Render Socratic Checkpoints
  renderCheckpoints(data.checkpoints, data.session_id);

  // Render Concept Primers
  renderPrimers(data.concept_anchors);

  // Render complete PDF export card
  renderExportTab(data);
}

// Render Slides
function renderSlidesDeck(slides, sessionId) {
  slidesDeck.innerHTML = "";
  if (!slides || slides.length === 0) {
    slidesDeck.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-muted); font-family: var(--font-mono); font-size: 11px;">NO SLIDES DETECTED</div>`;
    return;
  }

  slides.forEach(slide => {
    const card = document.createElement("div");
    card.className = "slide-card";
    card.id = `slide-card-${slide.id}`;
    card.dataset.slideId = slide.id;
    card.dataset.timestamp = slide.timestamp;

    const thumbUrl = `/api/slides/${sessionId}/${slide.thumb_filename}`;

    card.innerHTML = `
      <img src="${thumbUrl}" class="slide-thumb" alt="Slide ${slide.id}" loading="lazy">
      <div class="slide-meta">
        <span class="slide-time">${slide.formatted_time}</span>
        <span class="slide-title">Slide #${slide.id}</span>
      </div>
    `;

    card.addEventListener("click", () => {
      seekTo(slide.timestamp);
    });

    slidesDeck.appendChild(card);
  });
}

// Render Transcript with Distinct Lecture Speech & Color-Coded Outside AI Knowledge
function renderTranscript(segments) {
  transcriptStream.innerHTML = "";
  if (!segments || segments.length === 0) {
    transcriptStream.innerHTML = `<div class="empty-panel-state">No transcript available</div>`;
    return;
  }

  segments.forEach(seg => {
    const segDiv = document.createElement("div");
    const elab = seg.ai_elaboration;
    const elabType = elab ? elab.type : "none";

    segDiv.className = `transcript-segment`;
    segDiv.id = `seg-${seg.id}`;
    segDiv.dataset.segId = seg.id;
    segDiv.dataset.start = seg.start;
    segDiv.dataset.end = seg.end;
    segDiv.dataset.elaborationType = elabType;

    // Build word spans for exact word-level timeline sync
    let wordsHtml = "";
    if (seg.words && seg.words.length > 0) {
      wordsHtml = seg.words.map((w, wIdx) => {
        return `<span class="word-token" id="w-${seg.id}-${wIdx}" data-start="${w.start}" data-end="${w.end}">${escapeHtml(w.word)}</span> `;
      }).join("");
    } else {
      wordsHtml = escapeHtml(seg.text);
    }

    // Build outside knowledge callout if present
    let calloutHtml = "";
    if (elab && elab.content) {
      const rawBadge = (elab.badge || "").replace(/\(.*?\)/g, "").replace(/[\[\]]/g, "").trim().toUpperCase();
      let cleanBadge = "KEY CONCEPT";
      if (rawBadge.includes("PITFALL") || elab.type === "exam_pitfall" || rawBadge.includes("MISCONCEPTION")) {
        cleanBadge = "COMMON MISCONCEPTION";
      } else if (rawBadge.includes("APPLICATION") || elab.type === "application") {
        cleanBadge = "PRACTICAL APPLICATION";
      } else if (rawBadge.includes("PREREQUISITE") || elab.type === "prerequisite") {
        cleanBadge = "BACKGROUND KNOWLEDGE";
      } else if (rawBadge.includes("INTUITION") || elab.type === "intuition") {
        cleanBadge = "KEY CONCEPT";
      } else if (rawBadge) {
        cleanBadge = rawBadge;
      }

      calloutHtml = `
        <div class="ai-elaboration-callout callout-${escapeHtml(elab.type)}">
          <div class="callout-header">
            <span class="callout-badge">${escapeHtml(cleanBadge)}</span>
            <span class="callout-title">${escapeHtml(elab.title)}</span>
          </div>
          <div class="callout-content">${escapeHtml(elab.content)}</div>
        </div>
      `;
    }

    segDiv.innerHTML = `
      <div class="seg-time">${formatTime(seg.start)}</div>
      <div class="seg-body">
        <div class="spoken-lecture-text">
          ${wordsHtml}
        </div>
        ${calloutHtml}
      </div>
    `;

    // Click segment or word to jump
    segDiv.addEventListener("click", (e) => {
      // Don't seek if clicking inside the callout box text
      if (e.target.closest(".ai-elaboration-callout")) return;

      if (e.target.classList.contains("word-token")) {
        const wordStart = parseFloat(e.target.dataset.start);
        seekTo(wordStart);
      } else {
        seekTo(seg.start);
      }
    });

    transcriptStream.appendChild(segDiv);
  });

  applyTranscriptFilters();
}


// Render Socratic Checkpoints
function renderCheckpoints(checkpoints, sessionId) {
  checkpointsList.innerHTML = "";
  if (!checkpoints || checkpoints.length === 0) {
    checkpointsList.innerHTML = `<div class="empty-panel-state">No recall checkpoints generated</div>`;
    return;
  }

  checkpoints.forEach((chk, idx) => {
    const card = document.createElement("div");
    card.className = "socratic-card";
    card.id = `chk-card-${chk.id}`;

    const optsHtml = chk.options.map((opt, optIdx) => `
      <button class="chk-option-btn" data-chk-id="${chk.id}" data-opt-idx="${optIdx}">
        <strong style="font-family: var(--font-mono); margin-right: 4px;">${String.fromCharCode(65 + optIdx)}:</strong> ${escapeHtml(opt)}
      </button>
    `).join("");

    card.innerHTML = `
      <div class="chk-header">
        <span>Checkpoint ${idx + 1} · ${formatTime(chk.timestamp)}</span>
        <button class="btn-tech" style="padding: 2px 8px; font-size: 11px;" onclick="seekTo(${chk.timestamp})">
          <svg class="icon-svg" style="width: 11px; height: 11px;" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/></svg>
          Jump to Time
        </button>
      </div>
      <div class="chk-question">${escapeHtml(chk.question)}</div>
      <div class="chk-options">${optsHtml}</div>
      <div class="chk-explanation" id="chk-exp-${chk.id}" style="display: none;"></div>
    `;

    // Add option button click handlers
    card.querySelectorAll(".chk-option-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const optIdx = parseInt(btn.dataset.optIdx);
        await submitCheckpointAnswer(sessionId, chk.id, optIdx, card, chk);
      });
    });

    checkpointsList.appendChild(card);
  });
}

// Handle Checkpoint Answer
async function submitCheckpointAnswer(sessionId, chkId, optIdx, card, chk) {
  try {
    const res = await fetch("/api/checkpoint/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        checkpoint_id: chkId,
        selected_index: optIdx
      })
    });
    const result = await res.json();

    const buttons = card.querySelectorAll(".chk-option-btn");
    buttons.forEach((b, idx) => {
      b.disabled = true;
      if (idx === result.correct_index) {
        b.classList.add("selected", "correct");
      } else if (idx === optIdx && !result.is_correct) {
        b.classList.add("selected", "incorrect");
      }
    });

    const expDiv = card.querySelector(`#chk-exp-${chkId}`);
    expDiv.style.display = "block";
    expDiv.innerHTML = `
      <strong style="color: ${result.is_correct ? 'var(--accent-green)' : 'var(--accent-red)'}">
        ${result.is_correct ? 'Correct' : 'Incorrect'}
      </strong><br>
      <div style="margin-top: 4px; line-height: 1.45;">${escapeHtml(result.explanation)}</div>
    `;

    card.classList.add("completed");
  } catch (err) {
    console.error("Error submitting answer:", err);
  }
}

// Render Concept Definitions
function renderPrimers(anchors) {
  primersList.innerHTML = "";
  if (!anchors || anchors.length === 0) {
    primersList.innerHTML = `<div class="empty-panel-state">No explicit definitions detected</div>`;
    return;
  }

  anchors.forEach(a => {
    const item = document.createElement("div");
    item.className = "concept-item";
    item.innerHTML = `
      <div class="concept-term">
        <span>${escapeHtml(a.term)}</span>
        <span class="concept-time" style="display: inline-flex; align-items: center; gap: 4px;">
          <svg class="icon-svg" style="width: 10px; height: 10px;" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          ${formatTime(a.timestamp)}
        </span>
      </div>
      <div class="concept-primer">${escapeHtml(a.primer)}</div>
    `;
    item.addEventListener("click", () => seekTo(a.timestamp));
    primersList.appendChild(item);
  });
}

// Render complete study guide PDF export card & stats
function renderExportTab(data) {
  const statsEl = document.getElementById("export-pdf-stats");
  if (!statsEl || !data) return;

  const qCount = data.checkpoints ? data.checkpoints.length : 0;
  const cCount = data.concept_anchors ? data.concept_anchors.length : 0;
  const elabCount = data.segments ? data.segments.filter(s => s.ai_elaboration && s.ai_elaboration.content).length : 0;
  const segCount = data.segments ? data.segments.length : 0;
  const durationStr = data.duration_formatted || formatTime(data.duration || 0);
  const words = data.total_words ? data.total_words.toLocaleString() : (data.segments ? data.segments.reduce((acc, s) => acc + (s.text ? s.text.split(" ").length : 0), 0).toLocaleString() : "0");

  statsEl.innerHTML = `
    <div class="pdf-stats-grid">
      <div class="pdf-stat-item">
        <span class="pdf-stat-num">${qCount} Questions</span>
        <span class="pdf-stat-lbl">Active Recall with Explanations</span>
      </div>
      <div class="pdf-stat-item">
        <span class="pdf-stat-num">${cCount} Concepts</span>
        <span class="pdf-stat-lbl">Core Definitions & Primers</span>
      </div>
      <div class="pdf-stat-item">
        <span class="pdf-stat-num">${elabCount} AI Callouts</span>
        <span class="pdf-stat-lbl">Key Concepts, Misconceptions & Applications</span>
      </div>
      <div class="pdf-stat-item">
        <span class="pdf-stat-num">${segCount} Segments</span>
        <span class="pdf-stat-lbl">Full Timeline (${durationStr}, ${words} words)</span>
      </div>
    </div>
  `;
}

// Seek video to timestamp
function seekTo(timestampSec) {
  if (video.srcObject) return; // Do not seek during live capture
  video.currentTime = Math.max(0, timestampSec);
  video.play().catch(() => {});
}

// Video timeupdate handler (sync slide and transcript)
function onVideoTimeUpdate() {
  if (video.srcObject) return; // Live broadcast active
  const curTime = video.currentTime;
  const duration = video.duration || 0;
  timeDisplay.innerText = `${formatTime(curTime)} / ${formatTime(duration)}`;

  if (!currentSession) return;

  // 1. Sync Slide
  if (currentSession.slides && currentSession.slides.length > 0) {
    let activeSlide = null;
    for (let i = 0; i < currentSession.slides.length; i++) {
      const s = currentSession.slides[i];
      if (curTime >= s.timestamp && (s.end_timestamp ? curTime < s.end_timestamp : true)) {
        activeSlide = s;
        break;
      }
    }
    if (activeSlide && activeSlide.id !== currentSlideId) {
      currentSlideId = activeSlide.id;
      document.querySelectorAll(".slide-card").forEach(c => c.classList.remove("active"));
      const activeCard = document.getElementById(`slide-card-${activeSlide.id}`);
      if (activeCard) {
        activeCard.classList.add("active");
        activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
      const indicator = document.getElementById("current-slide-indicator");
      if (indicator) indicator.innerText = `SYNC: SLIDE #${activeSlide.id} [${activeSlide.formatted_time}]`;
    }
  }

  // 2. Sync Transcript Segment
  if (currentSession.segments && currentSession.segments.length > 0) {
    let activeSeg = null;
    for (let i = 0; i < currentSession.segments.length; i++) {
      const seg = currentSession.segments[i];
      if (curTime >= seg.start && curTime <= seg.end) {
        activeSeg = seg;
        break;
      }
    }

    if (activeSeg && activeSeg.id !== currentSegId) {
      currentSegId = activeSeg.id;
      document.querySelectorAll(".transcript-segment").forEach(s => s.classList.remove("active-seg"));
      const activeDiv = document.getElementById(`seg-${activeSeg.id}`);
      if (activeDiv) {
        activeDiv.classList.add("active-seg");
        activeDiv.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }

    // 3. Highlight exact word token
    if (activeSeg && activeSeg.words) {
      document.querySelectorAll(".word-token.active-word").forEach(w => w.classList.remove("active-word"));
      for (let wIdx = 0; wIdx < activeSeg.words.length; wIdx++) {
        const w = activeSeg.words[wIdx];
        if (curTime >= w.start && curTime <= w.end) {
          const wSpan = document.getElementById(`w-${activeSeg.id}-${wIdx}`);
          if (wSpan) wSpan.classList.add("active-word");
          break;
        }
      }
    }
  }
}

// Ingest video modal flow
async function startIngest() {
  const videoPath = document.getElementById("input-video-path").value.trim();
  const durVal = document.getElementById("input-duration-limit").value.trim();
  const maxDuration = durVal ? parseFloat(durVal) : null;

  if (!videoPath) {
    alert("Please provide a valid video file path.");
    return;
  }

  const progressContainer = document.getElementById("modal-progress-container");
  const progressBar = document.getElementById("modal-progress-bar");
  const statusText = document.getElementById("modal-status-text");
  const startBtn = document.getElementById("btn-start-process");

  progressContainer.style.display = "block";
  startBtn.disabled = true;

  try {
    const res = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_path: videoPath,
        max_duration_sec: maxDuration
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Processing start failed");
    }

    const data = await res.json();
    activeJobId = data.job_id;

    // Poll job progress
    jobPollTimer = setInterval(async () => {
      try {
        const jobRes = await fetch(`/api/job/${activeJobId}`);
        if (!jobRes.ok) return;
        const job = await jobRes.json();

        progressBar.style.width = `${job.progress}%`;
        statusText.innerText = job.status_message || `Progress: ${job.progress}%`;

        if (job.status === "completed") {
          clearInterval(jobPollTimer);
          document.getElementById("process-modal").style.display = "none";
          startBtn.disabled = false;
          progressContainer.style.display = "none";
          loadSession(job.session_id);
        } else if (job.status === "error") {
          clearInterval(jobPollTimer);
          startBtn.disabled = false;
          statusText.innerHTML = `<span style="color: var(--accent-red)">Error: ${job.error}</span>`;
        }
      } catch (pollErr) {
        console.error("Poll error:", pollErr);
      }
    }, 1200);

  } catch (err) {
    alert("Failed to start processing: " + err.message);
    startBtn.disabled = false;
    progressContainer.style.display = "none";
  }
}

// Sessions modal
async function openSessionsModal() {
  const container = document.getElementById("sessions-list-container");
  container.innerHTML = `<div style="padding: 10px; font-family: var(--font-mono); font-size: 11px;">Loading sessions...</div>`;
  document.getElementById("sessions-modal").style.display = "flex";

  const sessions = await fetchSessions();
  if (sessions.length === 0) {
    container.innerHTML = `<div style="padding: 14px; font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">No sessions recorded yet.</div>`;
    return;
  }

  container.innerHTML = sessions.map(s => `
    <div style="background: var(--bg-main); border: 1px solid var(--border-color); padding: 8px 10px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; border-radius: 2px;">
      <div>
        <div style="font-weight: 600; font-size: 12px; color: var(--text-primary);">${escapeHtml(s.video_title)}</div>
        <div style="font-family: var(--font-mono); font-size: 10px; color: var(--text-secondary); margin-top: 2px;">
          DUR: ${s.duration_formatted} | SLIDES: ${s.total_slides} | WORDS: ${s.total_words.toLocaleString()}
        </div>
      </div>
      <div style="display: flex; gap: 6px;">
        <button class="btn-tech" onclick="openReprocessModalFor('${s.session_id}', '${escapeHtml(s.video_title)}')">↻ REPROCESS</button>
        <button class="btn-tech btn-primary" onclick="selectSessionFromModal('${s.session_id}')">LOAD</button>
      </div>
    </div>
  `).join("");
}

function selectSessionFromModal(sessionId) {
  document.getElementById("sessions-modal").style.display = "none";
  loadSession(sessionId);
}

// REPROCESSING WORKFLOW (FAST AI RE-SYNTHESIS & FULL REPROCESS)
function openReprocessModalFor(sessionId, sessionTitle) {
  const modal = document.getElementById("reprocess-modal");
  modal.dataset.sessionId = sessionId;
  const titleEl = document.getElementById("reprocess-session-title");
  if (titleEl) titleEl.innerText = sessionTitle || sessionId;
  modal.style.display = "flex";
}

async function triggerReprocess(mode, sessionId) {
  const reprocessModal = document.getElementById("reprocess-modal");
  if (reprocessModal) reprocessModal.style.display = "none";
  const sessionsModal = document.getElementById("sessions-modal");
  if (sessionsModal) sessionsModal.style.display = "none";

  const toast = document.getElementById("processing-toast");
  const progressBar = document.getElementById("toast-progress-bar");
  const statusText = document.getElementById("toast-status-text");

  if (toast) {
    toast.style.display = "block";
    progressBar.style.width = mode === "ai" ? "30%" : "10%";
    statusText.innerText = mode === "ai"
      ? "Regenerating Socratic recall & study artifacts with active AI..."
      : "Queuing full lecture pipeline reprocessing...";
  }

  try {
    const res = await fetch(`/api/session/${sessionId}/reprocess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Reprocessing failed");
    }

    const data = await res.json();

    if (mode === "ai") {
      if (progressBar) progressBar.style.width = "100%";
      if (statusText) statusText.innerText = "Active recall & artifacts regenerated with AI.";
      await loadSession(sessionId);
      setTimeout(() => {
        if (toast) toast.style.display = "none";
      }, 1500);

    } else {
      // Full reprocessing runs as background job
      const jobId = data.job_id;
      const pollTimer = setInterval(async () => {
        try {
          const jobRes = await fetch(`/api/job/${jobId}`);
          if (!jobRes.ok) return;
          const job = await jobRes.json();

          if (progressBar) progressBar.style.width = `${job.progress}%`;
          if (statusText) statusText.innerText = job.status_message || `Reprocessing: ${job.progress}%`;

          if (job.status === "completed") {
            clearInterval(pollTimer);
            if (statusText) statusText.innerText = "Full session reprocessed successfully.";
            await loadSession(sessionId);
            setTimeout(() => {
              if (toast) toast.style.display = "none";
            }, 1500);
          } else if (job.status === "error") {
            clearInterval(pollTimer);
            if (statusText) statusText.innerHTML = `<span style="color: var(--accent-red)">Error: ${job.error}</span>`;
          }
        } catch (pollErr) {
          console.error("Reprocess poll error:", pollErr);
        }
      }, 1200);
    }

  } catch (err) {
    alert("Reprocessing error: " + err.message);
    if (toast) toast.style.display = "none";
  }
}


function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// DIRECT SCREEN & BROWSER TAB RECORDING
let screenStream = null;
let mediaRecorder = null;
let recordedBlobs = [];
let recTimerInterval = null;
let recSeconds = 0;

async function startScreenRecording() {
  try {
    // Request tab/window/screen display stream with system audio
    // displaySurface: "browser" hints the browser to prioritize the active Chrome / Edge Tabs tab!
    const displayStream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        displaySurface: "browser",
        cursor: "always",
        frameRate: { ideal: 30, max: 30 }
      },
      audio: true
    });

    // Check if the user selected 'Share audio' in the browser dialog
    let streamToRecord = displayStream;
    let micStream = null;
    if (displayStream.getAudioTracks().length === 0) {
      console.warn("No tab/system audio captured in displayStream. Attempting microphone fallback...");
      try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const micTrack = micStream.getAudioTracks()[0];
        if (micTrack) {
          streamToRecord = new MediaStream([
            ...displayStream.getVideoTracks(),
            micTrack
          ]);
        }
      } catch (micErr) {
        console.warn("Microphone fallback unavailable or denied:", micErr);
      }
    }

    screenStream = streamToRecord;

    // Attach stream directly to center stage video player!
    video.srcObject = displayStream;
    video.muted = true; // Prevent acoustic feedback while capturing live tab
    video.play().catch(() => {});

    // Show live broadcast overlays
    const liveStageHud = document.getElementById("live-stage-hud");
    if (liveStageHud) liveStageHud.style.display = "flex";

    const topBanner = document.getElementById("live-rec-top-banner");
    if (topBanner) topBanner.style.display = "inline-flex";

    const openRecBtn = document.getElementById("btn-open-record");
    if (openRecBtn) openRecBtn.style.display = "none";

    const videoTrack = displayStream.getVideoTracks()[0];
    if (videoTrack) {
      videoTrack.onended = () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
          stopScreenRecording();
        }
      };
    }

    // Set up MediaRecorder
    recordedBlobs = [];
    let options = { mimeType: 'video/webm;codecs=vp9,opus' };
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      options = { mimeType: 'video/webm;codecs=vp8,opus' };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = { mimeType: 'video/webm' };
      }
    }

    mediaRecorder = new MediaRecorder(streamToRecord, options);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordedBlobs.push(event.data);
      }
    };

    mediaRecorder.onstop = handleRecordingStopped;
    mediaRecorder.start(1000); // 1-second chunks

    // Start Timer
    recSeconds = 0;
    const updateTimerDisplays = () => {
      const h = Math.floor(recSeconds / 3600);
      const m = Math.floor((recSeconds % 3600) / 60);
      const s = recSeconds % 60;
      const str = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
      
      const stageTimer = document.getElementById("live-stage-timer");
      if (stageTimer) stageTimer.innerText = str;
      const topTimer = document.getElementById("top-rec-timer");
      if (topTimer) topTimer.innerText = str;
    };
    updateTimerDisplays();

    recTimerInterval = setInterval(() => {
      recSeconds++;
      updateTimerDisplays();
    }, 1000);

  } catch (err) {
    console.error("Direct screen/tab capture error:", err);
    // User cancelled browser picker or permission denied
  }
}

function stopScreenRecording() {
  if (recTimerInterval) {
    clearInterval(recTimerInterval);
    recTimerInterval = null;
  }
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  cleanupRecordingStream();
}

function cleanupRecordingStream() {
  if (recTimerInterval) {
    clearInterval(recTimerInterval);
    recTimerInterval = null;
  }
  if (screenStream) {
    screenStream.getTracks().forEach(t => t.stop());
    screenStream = null;
  }
  const liveStageHud = document.getElementById("live-stage-hud");
  if (liveStageHud) liveStageHud.style.display = "none";

  const topBanner = document.getElementById("live-rec-top-banner");
  if (topBanner) topBanner.style.display = "none";

  const openRecBtn = document.getElementById("btn-open-record");
  if (openRecBtn) openRecBtn.style.display = "inline-flex";

  video.srcObject = null;
  video.muted = false;
}

async function handleRecordingStopped() {
  const toast = document.getElementById("processing-toast");
  const progressBar = document.getElementById("toast-progress-bar");
  const statusText = document.getElementById("toast-status-text");

  if (toast) {
    toast.style.display = "block";
    progressBar.style.width = "10%";
    statusText.innerText = "Uploading captured lecture recording...";
  }

  try {
    const superBuffer = new Blob(recordedBlobs, { type: 'video/webm' });
    const sizeMb = (superBuffer.size / (1024 * 1024)).toFixed(1);
    if (statusText) statusText.innerText = `Ingesting ${sizeMb}MB class capture into Audilect...`;

    const formData = new FormData();
    formData.append("file", superBuffer, `class_capture_${Date.now()}.webm`);
    formData.append("title", `Captured Class (${new Date().toLocaleTimeString()})`);

    const res = await fetch("/api/record/upload", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    const data = await res.json();
    const jobId = data.job_id;

    // Poll background job progress
    const pollInterval = setInterval(async () => {
      try {
        const jobRes = await fetch(`/api/job/${jobId}`);
        if (!jobRes.ok) return;
        const job = await jobRes.json();

        if (progressBar) progressBar.style.width = `${job.progress}%`;
        if (statusText) statusText.innerText = job.status_message || `Progress: ${job.progress}%`;

        if (job.status === "completed") {
          clearInterval(pollInterval);
          if (toast) toast.style.display = "none";
          loadSession(job.session_id);
        } else if (job.status === "error") {
          clearInterval(pollInterval);
          if (statusText) {
            statusText.innerHTML = `<span style="color: var(--accent-red)">Error: ${job.error}</span>`;
          }
        }
      } catch (pErr) {
        console.error("Poll error:", pErr);
      }
    }, 1200);

  } catch (err) {
    alert("Error uploading captured class: " + err.message);
    if (toast) toast.style.display = "none";
  }
}

// Start
window.addEventListener("DOMContentLoaded", init);
