/* ═══════════════════════════════════════════════════
   AI-Medikelizar — Main Application Script
   ═══════════════════════════════════════════════════ */

"use strict";

(function () {
  /* ─── Backend API URL ───
     Automatically uses localhost:8000 during development and the
     same origin (relative URL) when deployed on Vercel (frontend
     and API are served from the same domain).
     Override by setting the SCRIPT_URL env var at build time. */
  const API_BASE = (
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === ""
  )
    ? "http://localhost:8000"
    : "";    // same origin → relative URLs work

  /* ─── State ─── */
  const state = {
    currentView: "home",
    query: "",
    results: null,
    isStreaming: false,
    followCount: 0,
    conversation: [], // { role: "user"|"assistant", query, answerHtml, sources }
  };

  /* ─── Demo evidence data ─── */
  // Example sources that would normally come from the RAG pipeline
  const demoSources = [
    {
      id: 1,
      title: "Evidence-based guideline for the management of hypertension in adults: 2014 report from the panel members appointed to the Eighth Joint National Committee (JNC 8)",
      authors: "James PA, Oparil S, Carter BL, et al.",
      journal: "JAMA",
      date: "2014-02-05",
      volume: "311(5):507-520",
      doi: "10.1001/jama.2013.284427",
      pmid: "24352797",
      url: "https://pubmed.ncbi.nlm.nih.gov/24352797/",
      abstract:
        "The JNC 8 panel recommends initiating pharmacologic treatment to lower blood pressure in adults aged ≥60 years to a goal of <150/90 mmHg and in adults aged 30-59 years to a goal of <140/90 mmHg. For the general nonblack population, initial treatment should include a thiazide-type diuretic, calcium channel blocker (CCB), angiotensin-converting enzyme inhibitor (ACEI), or angiotensin receptor blocker (ARB). For the general black population, initial treatment should include a thiazide-type diuretic or CCB.",
      publisher: "American Medical Association",
      relevance: 0.94,
    },
    {
      id: 2,
      title: "2017 ACC/AHA/AAPA/ABC/ACPM/AGS/APhA/ASH/ASPC/NMA/PCNA Guideline for the Prevention, Detection, Evaluation, and Management of High Blood Pressure in Adults",
      authors: "Whelton PK, Carey RM, Aronow WS, et al.",
      journal: "Hypertension / Journal of the American College of Cardiology",
      date: "2018-06-01",
      volume: "71(6):e13-e115",
      doi: "10.1161/HYP.0000000000000065",
      pmid: "29133356",
      url: "https://pubmed.ncbi.nlm.nih.gov/29133356/",
      abstract:
        "The 2017 ACC/AHA guideline lowered the threshold for defining hypertension to ≥130/80 mmHg and recommends a target of <130/80 mmHg for most adults. First-line antihypertensive agents include thiazide diuretics, CCBs, ACEIs, and ARBs. In black adults with hypertension, initial treatment should include a thiazide diuretic or CCB.",
      publisher: "American College of Cardiology / American Heart Association",
      relevance: 0.96,
    },
    {
      id: 3,
      title: "Pharmacologic Treatment of Hypertension in Adults: A Systematic Review and Network Meta-Analysis",
      authors: "Chen X, Zhang Y, Liu T, et al.",
      journal: "Annals of Internal Medicine",
      date: "2023-04-18",
      volume: "176(4):522-533",
      doi: "10.7326/M22-3103",
      pmid: "36940477",
      url: "https://pubmed.ncbi.nlm.nih.gov/36940477/",
      abstract:
        "This network meta-analysis of over 60 randomized trials found that thiazide-like diuretics, ACEIs, ARBs, and CCBs all significantly reduce major cardiovascular events compared to placebo. Combination therapy is more effective than monotherapy in achieving blood pressure targets. Low-dose combination therapy improves adherence and reduces side effects.",
      publisher: "American College of Physicians",
      relevance: 0.89,
    },
  ];

  /* ─── DOM refs ─── */
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const views = $$(".view");
  const navLinks = $$(".nav-link");
  const navToggle = $(".nav-toggle");
  const navList = $(".nav-list");
  const queryForm = $("#query-form");
  const queryInput = $("#query-input");
  const exampleBtns = $$(".example-btn");
  const resultsView = $("#results");
  const answerLoading = $("#answer-loading");
  const answerContent = $("#answer-content");
  const answerBody = $("#answer-body");
  const queryEchoText = $("#query-echo-text");
  const sourcesSection = $("#sources-section");
  const sourceCards = $("#source-cards");
  const sourcesCountBadge = $("#sources-count-badge");
  const answerSourcesCount = $("#answer-sources-count");
  const confidenceValue = $("#confidence-value");
  const answerTimestamp = $("#answer-timestamp");
  const confidenceOptions = $$(".confidence-option");
  const confidenceHint = $("#confidence-hint");

  /* ─── Follow-up DOM refs ─── */
  const followupBar = $("#followup-bar");
  const followupForm = $("#followup-form");
  const followupInput = $("#followup-input");
  const conversationHistory = $("#conversation-history");
  /* ─── Router ─── */
  function route(hash) {
    const viewId = hash.replace(/^#/, "") || "home";
    showView(viewId);
    updateActiveNav(viewId);
    closeMobileNav();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showView(viewId) {
    views.forEach((v) => v.classList.remove("active"));
    const target = document.getElementById(viewId);
    if (target) {
      target.classList.add("active");
      state.currentView = viewId;
    } else {
      // Fallback to home
      document.getElementById("home").classList.add("active");
      state.currentView = "home";
    }
  }

  function updateActiveNav(viewId) {
    navLinks.forEach((link) => {
      link.classList.toggle("active", link.getAttribute("href") === "#" + viewId);
    });
  }

  function closeMobileNav() {
    navToggle.setAttribute("aria-expanded", "false");
    navList.classList.remove("open");
  }

  /* ─── Mobile nav toggle ─── */
  navToggle.addEventListener("click", () => {
    const expanded = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!expanded));
    navList.classList.toggle("open");
  });

  /* ─── Navigation clicks ─── */
  document.addEventListener("click", (e) => {
    const navItem = e.target.closest("[data-nav]");
    if (navItem) {
      e.preventDefault();
      const href = navItem.getAttribute("href");
      if (href && href.startsWith("#")) {
        window.location.hash = href.slice(1);
      }
    }
  });

  /* ─── Hash change ─── */
  window.addEventListener("hashchange", () => route(window.location.hash));

  /* ─── Query submission ─── */
  queryForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;
    submitQuery(query);
  });

  /* ─── Follow-up form submission ─── */
  followupForm.addEventListener("submit", handleFollowup);

  /* ─── Confidence selector interactivity ─── */
  function getConfidence() {
    const checked = document.querySelector('input[name="confidence"]:checked');
    return checked ? checked.value : "medium";
  }

  function updateConfidenceHint(value) {
    const hints = {
      low: "Fewer sources, fastest response",
      medium: "Balanced speed and thoroughness",
      high: "Most sources, slower but comprehensive",
    };
    if (confidenceHint) confidenceHint.textContent = hints[value] || "";

    // Update active label styling
    confidenceOptions.forEach((opt) => {
      opt.classList.toggle("active", opt.getAttribute("data-confidence") === value);
    });
  }

  confidenceOptions.forEach((opt) => {
    opt.addEventListener("click", (e) => {
      // Don't re-trigger on inner label clicks if already the radio input
      if (e.target.tagName === "INPUT") return;
      const radio = opt.querySelector('input[type="radio"]');
      if (radio) {
        radio.checked = true;
        updateConfidenceHint(radio.value);
      }
    });

    // Also watch the native radio change event
    const radio = opt.querySelector('input[type="radio"]');
    if (radio) {
      radio.addEventListener("change", () => {
        if (radio.checked) {
          updateConfidenceHint(radio.value);
        }
      });
    }
  });

  /* ─── Example query buttons ─── */
  exampleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const query = btn.getAttribute("data-query");
      if (query) {
        queryInput.value = query;
        submitQuery(query);
      }
    });
  });

  /* ─── Submit query ─── */
  function submitQuery(query) {
    if (state.isStreaming) return;

    state.query = query;
    const confidence = getConfidence();

    // Clear previous results
    resetResults();

    // Navigate to results view
    window.location.hash = "results";

    // Set query echo
    queryEchoText.textContent = query;

    // Show confidence-aware loading message
    const loadingText = answerLoading.querySelector(".answer-loading-text");
    if (loadingText) {
      const loadingMsgs = {
        low: "Quick search in progress…",
        medium: "Retrieving evidence from trusted sources…",
        high: "Thorough search underway — this may take a moment…",
      };
      loadingText.textContent = loadingMsgs[confidence] || loadingMsgs.medium;
    }

    // Show loading
    answerLoading.hidden = false;
    answerContent.hidden = true;
    sourcesSection.hidden = true;

    state.isStreaming = true;

    // Try backend API first, fall back to demo
    fetchAnswerFromBackend(query, confidence).then((result) => {
      if (result) {
        displayBackendResult(result);
      } else {
        // Fallback: use demo data with confidence-aware delay
        const delays = { low: 300, medium: 800, high: 1800 };
        const delay = delays[confidence] || 800;
        setTimeout(() => {
          generateDemoAnswer(query);
        }, delay + Math.random() * 400);
      }
      state.isStreaming = false;
    });
  }

  /* ─── Show follow-up bar after answer ─── */
  function showFollowupBar() {
    followupBar.hidden = false;
    // Small delay before enabling focus
    setTimeout(() => followupInput.focus(), 300);
  }

  /* ─── Handle follow-up submission ─── */
  function handleFollowup(e) {
    e.preventDefault();
    const query = followupInput.value.trim();
    if (!query || state.isStreaming) return;
    followupInput.value = "";

    const confidence = getConfidence();

    // Create conversation entry container
    const entryIdx = state.followCount + 1;
    state.followCount++;

    const entry = document.createElement("div");
    entry.className = "conversation-entry";
    entry.id = `followup-entry-${entryIdx}`;
    entry.innerHTML = `
      <div class="query-echo">
        <span class="query-echo-label">Follow-up</span>
        <p class="query-echo-text">${escapeHtml(query)}</p>
      </div>
      <div class="answer-area">
        <div class="answer-loading" aria-live="polite">
          <div class="answer-loading-dot-pulse">
            <span class="sr-only">Retrieving evidence and generating answer</span>
          </div>
          <p class="answer-loading-text">Retrieving evidence for follow-up…</p>
        </div>
        <div class="answer-content" hidden>
          <div class="answer-header">
            <h2 class="answer-title">Synthesis</h2>
            <span class="answer-confidence">
              <span class="confidence-dot" aria-hidden="true"></span>
              <span class="confidence-label">Confidence</span>
              <span class="confidence-value">High</span>
            </span>
          </div>
          <div class="answer-body"></div>
          <div class="answer-meta">
            <span class="answer-date">Generated <time datetime=""></time></span>
            <span class="answer-sources-count"></span>
          </div>
        </div>
      </div>
      <div class="sources-section" hidden>
        <h2 class="section-label sources-section-label">
          Sources
          <span class="sources-count-badge">0</span>
        </h2>
        <div class="source-cards"></div>
      </div>
    `;

    conversationHistory.appendChild(entry);

    // Scroll to the new entry
    entry.scrollIntoView({ behavior: "smooth", block: "start" });

    state.isStreaming = true;

    // Build context from the last exchange (strip HTML for clean AI input)
    const lastExchange = state.conversation.length > 0
      ? state.conversation[state.conversation.length - 1]
      : null;
    const context = lastExchange
      ? {
          previousQuery: lastExchange.query,
          previousAnswer: stripHtml(lastExchange.answerHtml || "").slice(0, 800),
        }
      : null;

    console.log(`Follow-up context sent: previousQuery="${context?.previousQuery}"`);

    // Try backend with context, fall back to demo
    fetchAnswerFromBackend(query, confidence, context).then((result) => {
      if (result) {
        displayFollowupResult(entry, result, query);
      } else {
        const delays = { low: 300, medium: 800, high: 1800 };
        const delay = delays[confidence] || 800;
        setTimeout(() => {
          generateFollowupDemo(entry, query, context, query);
        }, delay + Math.random() * 400);
      }
      state.isStreaming = false;
    });

    // Hide follow-up bar slightly while loading, then show again
    followupBar.hidden = true;
  }

  /* ─── Escape HTML for safe rendering ─── */
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  /* ─── Strip HTML tags to get plain text ─── */
  function stripHtml(html) {
    const div = document.createElement("div");
    div.innerHTML = html;
    return div.textContent || div.innerText || "";
  }

  /* ─── Display follow-up result from backend ─── */
  function displayFollowupResult(entry, data, followupQuery) {
    const answerLoading = entry.querySelector(".answer-loading");
    const answerContent = entry.querySelector(".answer-content");
    const answerBody = entry.querySelector(".answer-body");
    const sourcesSection = entry.querySelector(".sources-section");
    const sourceCards = entry.querySelector(".source-cards");
    const sourcesCountBadge = entry.querySelector(".sources-count-badge");
    const answerSourcesCount = entry.querySelector(".answer-sources-count");
    const confidenceValue = entry.querySelector(".confidence-value");
    const answerTimestamp = entry.querySelector("time");

    const answerHtml = data.answer || "<p>No answer returned.</p>";
    const sources = (data.sources || []).map((s, i) => ({
      id: s.id || i + 1,
      title: s.title || "Untitled",
      authors: s.authors || "",
      journal: s.journal || "",
      date: s.date || "",
      volume: s.volume || "",
      doi: s.doi || "",
      pmid: s.pmid || "",
      url: s.url || "",
      abstract: s.abstract || "",
      publisher: s.publisher || "",
      relevance: s.relevance || 0.5,
    }));

    streamAnswerInEntry(answerBody, answerHtml, () => {
      answerLoading.hidden = true;
      answerContent.hidden = false;
      if (sources.length > 0) {
    renderSourceCardsInEntry(entry, sourceCards, sources, state.followCount);
    updateMetaInEntry(sourcesCountBadge, answerSourcesCount, confidenceValue, answerTimestamp, sources);
        sourcesSection.hidden = false;
      } else {
        sourcesSection.hidden = true;
      }
      showFollowupBar();
    });

    // Track conversation (store the actual follow-up query for context in future follow-ups)
    state.conversation.push({
      role: "assistant",
      query: followupQuery || "",
      answerHtml,
      sources,
    });
    console.log(`Follow-up tracked: query="${followupQuery}"`);
  }

  /* ─── Stream answer in a specific entry ─── */
  function streamAnswerInEntry(container, answerHtml, onComplete) {
    const temp = document.createElement("div");
    temp.innerHTML = answerHtml;
    const paragraphs = Array.from(temp.children);
    let idx = 0;
    container.innerHTML = "";

    function revealParagraphs() {
      if (idx >= paragraphs.length) {
        onComplete();
        return;
      }
      const p = document.createElement("p");
      p.innerHTML = paragraphs[idx].innerHTML;
      p.style.opacity = "0";
      p.style.transform = "translateY(4px)";
      p.style.transition = "opacity 0.35s ease, transform 0.35s ease";
      container.appendChild(p);
      requestAnimationFrame(() => {
        p.style.opacity = "1";
        p.style.transform = "translateY(0)";
      });
      idx++;
      const delay = 120 + Math.random() * 180;
      setTimeout(revealParagraphs, delay);
    }
    revealParagraphs();
  }

  /* ─── Render source cards in a specific entry ─── */
  function renderSourceCardsInEntry(entry, container, sources, entryIndex) {
    const idx = entryIndex || 0;
    container.innerHTML = sources
      .map(
        (s, i) => `
      <div class="source-card" data-source-id="${s.id}">          <button class="source-card-trigger" aria-expanded="false" aria-controls="source-panel-fu-${idx}-${s.id}">
          <span class="source-card-index">${i + 1}</span>
          <span class="source-card-body">
            <span class="source-card-title">${s.title}</span>
            <span class="source-card-meta-row">
              <span>${s.authors}</span>
              <span>${s.journal} · ${s.date}</span>
            </span>
          </span>
          <svg class="source-card-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
        <div class="source-card-detail-panel" id="source-panel-fu-${idx}-${s.id}" role="region">
          <p class="source-card-abstract">${s.abstract}</p>
          <div class="source-card-extras">
            <span>PMID: ${s.pmid}</span>
            <span>DOI: ${s.doi}</span>
            <span>Relevance: ${Math.round(s.relevance * 100)}%</span>
          </div>
          <a href="${s.url}" target="_blank" rel="noopener noreferrer" class="source-card-link">
            View on PubMed <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    `
      )
      .join("");

    // Set up expand/collapse for each card
    container.querySelectorAll(".source-card-trigger").forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const card = trigger.closest(".source-card");
        const isExpanded = card.classList.toggle("expanded");
        trigger.setAttribute("aria-expanded", String(isExpanded));
      });
    });
  }

  /* ─── Update meta in a specific entry ─── */
  function updateMetaInEntry(countBadge, sourcesCountEl, confidenceValEl, timestampEl, sources) {
    countBadge.textContent = sources.length;
    sourcesCountEl.textContent = `${sources.length} source${sources.length !== 1 ? "s" : ""}`;

    const maxRelevance = Math.max(...sources.map((s) => s.relevance));
    const dot = confidenceValEl.closest(".answer-confidence").querySelector(".confidence-dot");
    if (maxRelevance >= 0.9) {
      confidenceValEl.textContent = "High";
      if (dot) dot.className = "confidence-dot";
    } else if (maxRelevance >= 0.75) {
      confidenceValEl.textContent = "Moderate";
      if (dot) dot.className = "confidence-dot medium";
    } else {
      confidenceValEl.textContent = "Limited";
      if (dot) dot.className = "confidence-dot lower";
    }

    const now = new Date();
    timestampEl.textContent = now.toLocaleString("en-US", {
      month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  /* ─── Generate follow-up demo answer ─── */
  function generateFollowupDemo(entry, query, context, followupQuery) {
    const answerLoading = entry.querySelector(".answer-loading");
    const answerContent = entry.querySelector(".answer-content");
    const answerBody = entry.querySelector(".answer-body");
    const sourcesSection = entry.querySelector(".sources-section");
    const sourceCards = entry.querySelector(".source-cards");
    const sourcesCountBadge = entry.querySelector(".sources-count-badge");
    const answerSourcesCount = entry.querySelector(".answer-sources-count");
    const confidenceValue = entry.querySelector(".confidence-value");
    const answerTimestamp = entry.querySelector("time");

    // Use a subset of demoSources for variety, or reuse
    const followupSources = demoSources.slice(0, 2).map((s, i) => ({
      ...s,
      id: i + 100 + state.followCount,
    }));

    const s = (id) =>
      `<sup class="citation-marker" data-source-id="${id}" tabindex="0" role="button" aria-label="Source ${id}">[${id}]</sup>`;
    const sid = (offset) => followupSources[offset]?.id || 1;

    const followupAnswer = [
      `<p>Based on the available evidence from the retrieved sources${s(sid(0))}${s(sid(1))}, addressing your follow-up question regarding <em>${escapeHtml(query)}</em>:</p>`,
      `<p><strong>Regarding your inquiry.</strong> The reviewed literature indicates that the treatment principles discussed earlier apply consistently across related clinical scenarios${s(sid(0))}. Combination therapy remains the cornerstone of effective management, with ACE inhibitors and calcium channel blockers showing particular efficacy in the populations studied.</p>`,
      `<p><strong>Recent evidence.</strong> A meta-analysis of recent trials${s(sid(1))} confirms that early intervention with guideline-directed therapy significantly reduces long-term complication rates. The absolute risk reduction is most pronounced in patients with additional cardiovascular risk factors.</p>`,
      `<p><strong>Clinical context.</strong> As with any clinical decision, individual patient factors, comorbidities, and preferences should guide the final treatment choice. The sources cited provide detailed subgroup analyses that may help tailor the approach${s(sid(0))}${s(sid(1))}.</p>`,
    ].join("\n");

    answerContent.hidden = false;

    streamAnswerInEntry(answerBody, followupAnswer, () => {
      answerLoading.hidden = true;
      renderSourceCardsInEntry(entry, sourceCards, followupSources, state.followCount);
      updateMetaInEntry(sourcesCountBadge, answerSourcesCount, confidenceValue, answerTimestamp, followupSources);
      sourcesSection.hidden = false;
      showFollowupBar();
    });

    state.conversation.push({
      role: "assistant",
      query: followupQuery || "",
      answerHtml: followupAnswer,
      sources: followupSources,
    });
    console.log(`Follow-up tracked (demo): query="${followupQuery}"`);
  }

  /* ─── Reset results ─── */
  function resetResults() {
    answerLoading.hidden = true;
    answerContent.hidden = true;
    sourcesSection.hidden = true;
    answerBody.innerHTML = "";
    sourceCards.innerHTML = "";
    // Clear conversation history
    conversationHistory.innerHTML = "";
    state.conversation = [];
    state.followCount = 0;
    followupBar.hidden = true;
  }

  /* ─── Call the FastAPI backend ─── */
  async function fetchAnswerFromBackend(query, confidence, context) {
    try {
      const resp = await fetch(`${API_BASE}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, confidence, context }),
        signal: AbortSignal.timeout(120000), // 2-minute timeout
      });

      if (!resp.ok) {
        console.warn("Backend returned", resp.status, "— falling back to demo");
        return null;
      }

      const data = await resp.json();
      return data;
    } catch (err) {
      if (err.name === "TimeoutError") {
        console.warn("Backend timed out — falling back to demo");
      } else if (err.name === "TypeError" && err.message.includes("fetch")) {
        console.warn("Backend not reachable — falling back to demo");
      } else {
        console.warn("Backend error:", err.message, "— falling back to demo");
      }
      return null;
    }
  }

  /* ─── Display a result from the backend API ─── */
  function displayBackendResult(data) {
    answerContent.hidden = false;

    const answerHtml = data.answer || "<p>No answer returned.</p>";
    const sources = (data.sources || []).map((s, i) => ({
      id: s.id || i + 1,
      title: s.title || "Untitled",
      authors: s.authors || "",
      journal: s.journal || "",
      date: s.date || "",
      volume: s.volume || "",
      doi: s.doi || "",
      pmid: s.pmid || "",
      url: s.url || "",
      abstract: s.abstract || "",
      publisher: s.publisher || "",
      relevance: s.relevance || 0.5,
    }));

    streamAnswer(answerHtml, () => {
      answerLoading.hidden = true;
      if (sources.length > 0) {
        renderSourceCards(sources);
        updateMeta(sources);
      } else {
        sourcesSection.hidden = true;
      }
      showFollowupBar();
    });

    // Track the initial query/answer in conversation history
    state.conversation.push({
      role: "assistant",
      query: state.query,
      answerHtml,
      sources,
    });

    // Log provider info
    if (data.provider) {
      console.log(`Answered by: ${data.provider} · ${data.model}`);
    }
  }

  /* ─── Generate demo answer (fallback) ─── */
  function generateDemoAnswer(query) {
    const answerText = buildAnswer(query, demoSources);

    answerContent.hidden = false;

    streamAnswer(answerText, () => {
      answerLoading.hidden = true;
      renderSourceCards(demoSources);
      updateMeta(demoSources);
      showFollowupBar();
    });

    // Track the initial query/answer in conversation history
    state.conversation.push({
      role: "assistant",
      query: state.query,
      answerHtml: answerText,
      sources: demoSources,
    });
  }

  /* ─── Build answer text with citation markers ─── */
  function buildAnswer(query, sources) {
    // This simulates what the RAG + LLM pipeline would produce.
    // In production, this would come from the backend API.
    const s = (id) =>
      `<sup class="citation-marker" data-source-id="${id}" tabindex="0" role="button" aria-label="Source ${id}">[${id}]</sup>`;

    return [
      `<p>Based on the retrieved evidence from the JNC 8${s(1)}, 2017 ACC/AHA${s(2)}, and a recent network meta-analysis${s(3)}, the recommended first-line pharmacotherapy for hypertension in adults can be summarised as follows.</p>`,

      `<p><strong>Treatment thresholds and targets.</strong> The JNC 8 guideline${s(1)} recommends initiating pharmacologic treatment in adults aged ≥60 years at systolic blood pressure (SBP) ≥150 mmHg or diastolic (DBP) ≥90 mmHg, with a treatment goal of <150/90 mmHg. For adults aged 30–59 years, the threshold is ≥140/90 mmHg with a goal of <140/90 mmHg. The 2017 ACC/AHA guideline${s(2)} adopts a lower threshold, defining hypertension as ≥130/80 mmHg and recommending a target of <130/80 mmHg for most adults.</p>`,

      `<p><strong>First-line agents.</strong> For the general nonblack population, both the JNC 8${s(1)} and ACC/AHA${s(2)} guidelines recommend initial treatment with a <em>thiazide-type diuretic</em>, <em>calcium channel blocker (CCB)</em>, <em>angiotensin-converting enzyme inhibitor (ACEI)</em>, or <em>angiotensin receptor blocker (ARB)</em>. For the general black population, a thiazide-type diuretic or CCB is recommended as initial therapy due to differential efficacy data${s(1)}.${s(2)}</p>`,

      `<p><strong>Combination therapy.</strong> The network meta-analysis by Chen et al.${s(3)} found that combination therapy is significantly more effective than monotherapy in achieving blood pressure targets. Low-dose combination therapy (e.g., ACEI + CCB or thiazide + ARB) also improves adherence and reduces dose-dependent side effects compared to high-dose monotherapy.</p>`,

      `<p><strong>Key considerations.</strong> Choice of agent should account for comorbidities (e.g., diabetes, chronic kidney disease, heart failure), age, race/ethnicity, and tolerability. Beta-blockers are no longer recommended as first-line agents unless indicated for other conditions (e.g., coronary artery disease, heart failure). All three sources${s(1)}${s(2)}${s(3)} consistently prioritise thiazide-like diuretics, CCBs, ACEIs, and ARBs as first-line options.</p>`,
    ].join("\n");
  }

  /* ─── Stream answer text ─── */
  function streamAnswer(answerHtml, onComplete) {
    // Create a temporary container to parse the HTML
    const temp = document.createElement("div");
    temp.innerHTML = answerHtml;

    // Reveal paragraphs one by one with fade-in
    const paragraphs = Array.from(temp.children);
    let idx = 0;

    answerBody.innerHTML = "";

    function revealParagraphs() {
      if (idx >= paragraphs.length) {
        onComplete();
        return;
      }

      const p = document.createElement("p");
      p.innerHTML = paragraphs[idx].innerHTML;
      p.style.opacity = "0";
      p.style.transform = "translateY(4px)";
      p.style.transition = "opacity 0.35s ease, transform 0.35s ease";
      answerBody.appendChild(p);

      // Trigger animation
      requestAnimationFrame(() => {
        p.style.opacity = "1";
        p.style.transform = "translateY(0)";
      });

      idx++;

      const delay = 120 + Math.random() * 180;
      setTimeout(revealParagraphs, delay);
    }

    revealParagraphs();
  }

  /* ─── Render source cards ─── */
  function renderSourceCards(sources) {
    sourceCards.innerHTML = sources
      .map(
        (s, i) => `
      <div class="source-card" data-source-id="${s.id}">
        <button class="source-card-trigger" aria-expanded="false" aria-controls="source-panel-${s.id}">
          <span class="source-card-index">${i + 1}</span>
          <span class="source-card-body">
            <span class="source-card-title">${s.title}</span>
            <span class="source-card-meta-row">
              <span>${s.authors}</span>
              <span>${s.journal} · ${s.date}</span>
            </span>
          </span>
          <svg class="source-card-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
        <div class="source-card-detail-panel" id="source-panel-${s.id}" role="region" aria-labelledby="source-title-${s.id}">
          <p class="source-card-abstract">${s.abstract}</p>
          <div class="source-card-extras">
            <span>PMID: ${s.pmid}</span>
            <span>DOI: ${s.doi}</span>
            <span>Relevance: ${Math.round(s.relevance * 100)}%</span>
          </div>
          <a href="${s.url}" target="_blank" rel="noopener noreferrer" class="source-card-link">
            View on PubMed <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    `
      )
      .join("");

    sourcesSection.hidden = false;

    // Set up expand/collapse for each card
    sourceCards.querySelectorAll(".source-card-trigger").forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const card = trigger.closest(".source-card");
        const isExpanded = card.classList.toggle("expanded");
        trigger.setAttribute("aria-expanded", String(isExpanded));
      });
    });

    // Wire up citation markers in answer body to scroll to source
    answerBody.querySelectorAll(".citation-marker").forEach((marker) => {
      marker.addEventListener("click", () => {
        const id = marker.getAttribute("data-source-id");
        const targetCard = document.querySelector(`.source-card[data-source-id="${id}"]`);
        if (targetCard) {
          // Expand the card if not expanded
          const trigger = targetCard.querySelector(".source-card-trigger");
          if (!targetCard.classList.contains("expanded")) {
            targetCard.classList.add("expanded");
            trigger.setAttribute("aria-expanded", "true");
          }
          targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    });
  }

  /* ─── Update meta info ─── */
  function updateMeta(sources) {
    sourcesCountBadge.textContent = sources.length;
    answerSourcesCount.textContent = `${sources.length} source${sources.length !== 1 ? "s" : ""}`;

    // Set confidence based on highest relevance
    const maxRelevance = Math.max(...sources.map((s) => s.relevance));
    const dot = document.querySelector(".confidence-dot");
    if (maxRelevance >= 0.9) {
      confidenceValue.textContent = "High";
      dot.className = "confidence-dot";
    } else if (maxRelevance >= 0.75) {
      confidenceValue.textContent = "Moderate";
      dot.className = "confidence-dot medium";
    } else {
      confidenceValue.textContent = "Limited";
      dot.className = "confidence-dot lower";
    }

    // Timestamp
    const now = new Date();
    answerTimestamp.textContent = now.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /* ─── Keyboard shortcuts ─── */
  document.addEventListener("keydown", (e) => {
    // Escape to go home
    if (e.key === "Escape" && state.currentView !== "home") {
      window.location.hash = "home";
      queryInput.focus();
    }

    // Ctrl+/ or Cmd+/ to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === "/") {
      e.preventDefault();
      queryInput.focus();
    }
  });

  /* ─── Dark mode ─── */

  /** Detect system color scheme preference */
  function getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  /** Get the stored theme, falling back to system preference */
  function getStoredTheme() {
    const stored = localStorage.getItem("ai-medikelizar-theme");
    if (stored === "dark" || stored === "light") return stored;
    return null;
  }

  /** Apply theme to the document (always sets data-theme explicitly) */
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  /** Resolve and apply the correct theme */
  function resolveTheme() {
    const stored = getStoredTheme();
    const theme = stored || getSystemTheme();
    applyTheme(theme);
    return theme;
  }

  /** Update toggle button aria-label and title based on current theme */
  function updateToggleAria(themeToggle, currentTheme) {
    const nextTheme = currentTheme === "dark" ? "light" : "dark";
    const nextLabel = nextTheme === "dark" ? "dark" : "light";
    themeToggle.setAttribute("aria-label", `Switch to ${nextLabel} mode`);
    themeToggle.setAttribute("title", `Switch to ${nextLabel} mode`);
  }

  /** Toggle between light and dark */
  function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const newTheme = currentTheme === "dark" ? "light" : "dark";

    applyTheme(newTheme);
    localStorage.setItem("ai-medikelizar-theme", newTheme);

    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) updateToggleAria(themeToggle, newTheme);
  }

  /* ─── Pricing page ─── */
  let pricingTiers = [];
  let pricingAnnual = false;

  // Hardcoded fallback in case the backend API isn't running
  const PLACEHOLDER_TIERS = [
    {
      id: "basic",
      label: "Basic",
      price_cents: 0,
      queries_per_day: 5,
      features: [
        "5 queries per day",
        "Standard response speed",
        "Basic source citations",
        "Email support",
      ],
    },
    {
      id: "premium",
      label: "Premium",
      price_cents: 999,
      queries_per_day: 50,
      features: [
        "50 queries per day",
        "Faster response priority",
        "Detailed source citations",
        "Priority email support",
      ],
    },
    {
      id: "vip",
      label: "VIP",
      price_cents: 2999,
      queries_per_day: -1,
      features: [
        "Unlimited queries",
        "Fastest response priority",
        "Full source citations with abstracts",
        "Priority support (email + chat)",
        "Early access to new features",
      ],
    },
  ];

  async function loadPricing() {
    try {
      const resp = await fetch(`${API_BASE}/api/subscriptions/pricing`);
      if (!resp.ok) {
        throw new Error("Backend not available");
      }
      const data = await resp.json();
      pricingTiers = data.tiers || [];
    } catch (e) {
      console.warn("Pricing API unavailable, using placeholder:", e.message);
      pricingTiers = PLACEHOLDER_TIERS;
    }
    renderPricingCards();
    loadSubscriptionStatus();
  }

  function renderPricingCards() {
    const grid = document.getElementById("pricing-grid");
    if (!grid) return;

    grid.innerHTML = pricingTiers.map((tier) => {
      const isFree = tier.price_cents === 0;
      const price = pricingAnnual && !isFree
        ? Math.round(tier.price_cents * 0.8)
        : tier.price_cents;
      const priceDisplay = isFree ? "Free" : `$${(price / 100).toFixed(2)}`;
      const unit = isFree ? "" : pricingAnnual ? "/mo, billed annually" : "/month";
      const queriesDisplay = tier.queries_per_day === -1
        ? "Unlimited queries"
        : `${tier.queries_per_day} queries/day`;
      const featured = tier.id === "premium";

      return `
        <div class="pricing-card${featured ? ' pricing-card-featured' : ''}">
          ${featured ? '<div class="pricing-card-badge">Most Popular</div>' : ''}
          <div class="pricing-card-name">${tier.label}</div>
          <div class="pricing-card-price">${priceDisplay} <span class="pricing-card-price-unit">${unit}</span></div>
          <div class="pricing-card-desc">${queriesDisplay} · Standard response</div>
          <ul class="pricing-card-features">
            ${tier.features.map(f => `<li>${f}</li>`).join("")}
          </ul>
          <button class="btn ${isFree ? 'btn-secondary' : 'btn-primary'} pricing-subscribe-btn"
                  data-tier="${tier.id}"
                  data-free="${isFree}">
            ${isFree ? 'Current Plan' : 'Subscribe'}
          </button>
        </div>
      `;
    }).join("");

    // Wire subscribe buttons
    grid.querySelectorAll(".pricing-subscribe-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const tier = btn.getAttribute("data-tier");
        const isFree = btn.getAttribute("data-free") === "true";
        if (isFree) return;
        await subscribeToTier(tier);
      });
    });
  }

  async function subscribeToTier(tier) {
    try {
      const resp = await fetch(`${API_BASE}/api/subscriptions/create-checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(err.detail || "Failed to create checkout session");
        return;
      }
      const data = await resp.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (e) {
      console.error("Checkout error:", e);
      alert("Could not connect to payment server. Please try again.");
    }
  }

  async function loadSubscriptionStatus() {
    try {
      const resp = await fetch(`${API_BASE}/api/subscriptions/status`);
      if (!resp.ok) return;
      const status = await resp.json();

      const planCard = document.getElementById("pricing-current-plan");
      const planName = document.getElementById("current-plan-name");
      const planStatus = document.getElementById("current-plan-status");
      const planUsage = document.getElementById("current-plan-usage");

      if (planCard && status.tier) {
        planCard.hidden = false;
        if (planName) planName.textContent = status.tier.charAt(0).toUpperCase() + status.tier.slice(1);
        if (planStatus) {
          planStatus.textContent = status.status.charAt(0).toUpperCase() + status.status.slice(1);
          planStatus.className = `current-plan-status admin-status-${status.status}`;
        }
        if (planUsage) {
          const limitText = status.queries_limit === -1 ? "Unlimited" : status.queries_limit;
          planUsage.textContent = `Queries today: ${status.queries_used_today} / ${limitText}`;
        }
      }
    } catch (e) {
      console.warn("Failed to load subscription status:", e.message);
    }
  }

  // Pricing toggle (monthly/annual)
  const pricingToggle = document.getElementById("pricing-period-toggle");
  if (pricingToggle) {
    pricingToggle.addEventListener("click", () => {
      const checked = pricingToggle.getAttribute("aria-checked") === "true";
      pricingToggle.setAttribute("aria-checked", String(!checked));
      pricingAnnual = !checked;

      // Update label styling
      const monthly = document.getElementById("pricing-period-monthly");
      const annual = document.getElementById("pricing-period-annual");
      if (monthly) monthly.className = `pricing-toggle-label${pricingAnnual ? '' : ' pricing-toggle-label-active'}`;
      if (annual) annual.className = `pricing-toggle-label${pricingAnnual ? ' pricing-toggle-label-active' : ''}`;

      renderPricingCards();
    });
  }

  // Manage subscription button
  const manageBtn = document.getElementById("manage-subscription-btn");
  if (manageBtn) {
    manageBtn.addEventListener("click", async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/subscriptions/create-portal-session`, {
          method: "POST",
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.url) window.location.href = data.url;
      } catch (e) {
        console.error("Portal error:", e);
      }
    });
  }

  /* ─── Placeholder admin data ─── */
  const PLACEHOLDER_ADMIN_DATA = {
    total_users: 1234,
    new_users_7d: 47,
    total_queries: 28920,
    queries_7d: 1043,
    total_revenue_cents: 459900,
    revenue_7d_cents: 18500,
    active_subscriptions: 186,
    users_by_tier: { basic: 1048, premium: 142, vip: 44 },
    recent_users: [
      { email: "jane.doe@hospital.org", name: "Jane Doe", tier: "premium", subscription_status: "active", is_admin: false, created_at: "2026-07-15T10:30:00Z" },
      { email: "m.smith@clinic.com", name: "Marcus Smith", tier: "vip", subscription_status: "active", is_admin: true, created_at: "2026-07-14T08:15:00Z" },
      { email: "l.chen@medschool.edu", name: "Li Chen", tier: "basic", subscription_status: "active", is_admin: false, created_at: "2026-07-13T14:20:00Z" },
      { email: "a.patel@nhs.uk", name: "Anika Patel", tier: "premium", subscription_status: "active", is_admin: false, created_at: "2026-07-12T09:45:00Z" },
      { email: "r.johnson@va.gov", name: "Robert Johnson", tier: "basic", subscription_status: "cancelled", is_admin: false, created_at: "2026-07-10T16:00:00Z" },
      { email: "s.garcia@researchlab.io", name: "Sofia Garcia", tier: "vip", subscription_status: "active", is_admin: false, created_at: "2026-07-08T11:30:00Z" },
      { email: "t.wilson@medicare.gov", name: "Thomas Wilson", tier: "basic", subscription_status: "active", is_admin: false, created_at: "2026-07-05T07:00:00Z" },
      { email: "e.brown@pharma.com", name: "Emily Brown", tier: "premium", subscription_status: "past_due", is_admin: false, created_at: "2026-07-01T13:10:00Z" },
    ],
  };

  function renderAdminPlaceholder() {
    const data = PLACEHOLDER_ADMIN_DATA;

    const setStat = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setStat("stat-total-users", data.total_users.toLocaleString());
    setStat("stat-new-users", `+${data.new_users_7d}`);
    setStat("stat-total-queries", data.total_queries.toLocaleString());
    setStat("stat-queries-7d", data.queries_7d.toLocaleString());
    setStat("stat-total-revenue", `$${(data.total_revenue_cents / 100).toFixed(2)}`);
    setStat("stat-revenue-7d", `$${(data.revenue_7d_cents / 100).toFixed(2)}`);
    setStat("stat-active-subs", data.active_subscriptions);

    // Users by tier
    const tierEl = document.getElementById("stat-users-by-tier");
    if (tierEl && data.users_by_tier) {
      const parts = Object.entries(data.users_by_tier).map(
        ([tier, count]) => `${tier}: ${count}`
      );
      tierEl.textContent = parts.join(" · ") || "None";
      tierEl.style.fontSize = "0.875rem";
    }

    // Subscription breakdown
    const tierStats = data.users_by_tier || {};
    setStat("admin-tier-basic", tierStats.basic || 0);
    setStat("admin-tier-premium", tierStats.premium || 0);
    setStat("admin-tier-vip", tierStats.vip || 0);
    setStat("admin-monthly-revenue", `$${((data.total_revenue_cents || 0) / 100 * 0.33).toFixed(0)}/mo`);

    // Refresh timestamp
    const refreshEl = document.getElementById("admin-last-refresh");
    if (refreshEl) {
      refreshEl.textContent = `Placeholder data — last refreshed: ${new Date().toLocaleTimeString()}`;
    }

    // Render users table
    const tbody = document.getElementById("admin-users-body");
    if (tbody) {
      tbody.innerHTML = data.recent_users.length
        ? data.recent_users.map((u) => {
            const tierClass = `admin-tier-${u.tier}`;
            const statusClass = `admin-status-${u.subscription_status || "active"}`;
            const joined = new Date(u.created_at).toLocaleDateString();
            return `
              <tr>
                <td>${u.email}</td>
                <td>${u.name || "—"}</td>
                <td><span class="admin-tier-badge ${tierClass}">${u.tier}</span></td>
                <td class="${statusClass}">${u.subscription_status || "active"}</td>
                <td>${u.is_admin ? '<span class="admin-badge">Admin</span>' : ""}</td>
                <td>${joined}</td>
              </tr>
            `;
          }).join("")
        : '<tr><td colspan="6" class="admin-table-empty">No users yet</td></tr>';
    }
  }

  /* ─── Admin dashboard ─── */
  async function loadAdminDashboard() {
    try {
      const resp = await fetch(`${API_BASE}/api/admin/dashboard`);
      if (!resp.ok) {
        if (resp.status === 401 || resp.status === 403) {
          document.querySelector("#admin-users-body").innerHTML =
            '<tr><td colspan="6" class="admin-table-empty">Admin access required. Please sign in with an admin account.</td></tr>';
        } else {
          // Use placeholder data
          renderAdminPlaceholder();
        }
        return;
      }
      const data = await resp.json();

      // Update stats
      const setStat = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setStat("stat-total-users", data.total_users.toLocaleString());
      setStat("stat-new-users", `+${data.new_users_7d}`);
      setStat("stat-total-queries", data.total_queries.toLocaleString());
      setStat("stat-queries-7d", data.queries_7d.toLocaleString());
      setStat("stat-total-revenue", `$${(data.total_revenue_cents / 100).toFixed(2)}`);
      setStat("stat-revenue-7d", `$${(data.revenue_7d_cents / 100).toFixed(2)}`);
      setStat("stat-active-subs", data.active_subscriptions);

      // Users by tier
      const tierEl = document.getElementById("stat-users-by-tier");
      if (tierEl && data.users_by_tier) {
        const parts = Object.entries(data.users_by_tier).map(
          ([tier, count]) => `${tier}: ${count}`
        );
        tierEl.textContent = parts.join(" · ") || "None";
        tierEl.style.fontSize = "0.875rem";
      }

      // Subscription breakdown (from users_by_tier + revenue)
      const tierStats = data.users_by_tier || {};
      setStat("admin-tier-basic", tierStats.basic || 0);
      setStat("admin-tier-premium", tierStats.premium || 0);
      setStat("admin-tier-vip", tierStats.vip || 0);
      setStat("admin-monthly-revenue", `$${((data.total_revenue_cents || 0) / 100 * 0.33).toFixed(0)}/mo`);

      // Refresh timestamp
      const refreshEl = document.getElementById("admin-last-refresh");
      if (refreshEl) {
        refreshEl.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
      }

      // Render users table
      const tbody = document.getElementById("admin-users-body");
      if (tbody && data.recent_users) {
        tbody.innerHTML = data.recent_users.length
          ? data.recent_users.map((u) => {
              const tierClass = `admin-tier-${u.tier}`;
              const statusClass = `admin-status-${u.subscription_status || "active"}`;
              const joined = new Date(u.created_at).toLocaleDateString();
              return `
                <tr>
                  <td>${u.email}</td>
                  <td>${u.name || "—"}</td>
                  <td><span class="admin-tier-badge ${tierClass}">${u.tier}</span></td>
                  <td class="${statusClass}">${u.subscription_status || "active"}</td>
                  <td>${u.is_admin ? '<span class="admin-badge">Admin</span>' : ""}</td>
                  <td>${joined}</td>
                </tr>
              `;
            }).join("")
          : '<tr><td colspan="6" class="admin-table-empty">No users yet</td></tr>';
      }
    } catch (e) {
      console.warn("Failed to load admin dashboard, using placeholder:", e.message);
      renderAdminPlaceholder();
    }
  }

  // Admin refresh button
  const adminRefreshBtn = document.getElementById("admin-refresh-btn");
  if (adminRefreshBtn) {
    adminRefreshBtn.addEventListener("click", loadAdminDashboard);
  }

  // Admin shield button is always visible in the header

  /* ─── Route hook: init data on view changes ─── */
  const origShowView = showView;
  showView = function (viewId) {
    origShowView(viewId);

    if (viewId === "pricing") {
      loadPricing();
    } else if (viewId === "admin") {
      loadAdminDashboard();
    }

  };

  /* ─── Init ─── */
  function init() {
    // Set footer year
    const footerYear = document.getElementById("footer-year");
    if (footerYear) footerYear.textContent = new Date().getFullYear();

    // ── Note: AI provider & model are configured in .env (backend side) ──
    //    The backend logs them on startup; see .env.example for options.

    // ── Theme initialisation ──
    const currentTheme = resolveTheme();

    // Wire up theme toggle button
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      updateToggleAria(themeToggle, currentTheme);
      themeToggle.addEventListener("click", toggleTheme);
    }

    // Listen for system colour scheme changes (only if no stored preference)
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (!getStoredTheme()) {
        const newTheme = resolveTheme();
        if (themeToggle) updateToggleAria(themeToggle, newTheme);
      }
    });

    // Enable CSS transitions after a brief delay (avoids flash on load)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.documentElement.classList.add("theme-ready");
      });
    });

    // Initial route based on URL hash or default to home
    const hash = window.location.hash || "#home";
    route(hash);

    console.log(
      "%c⚕ AI-Medikelizar %cClinical Reference Tool",
      "font-family: Georgia, serif; font-weight: 700; font-size: 1.1rem; color: #1e2028;",
      "font-size: 0.85rem; color: #5a6170;"
    );
    console.log("This tool provides evidence-based medical information from trusted sources.");
    console.log("It is NOT a substitute for professional medical advice.");
  }

  init();
})();
