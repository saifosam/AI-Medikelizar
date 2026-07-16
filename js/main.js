/* ═══════════════════════════════════════════════════
   AI-Medikelizar — Main Application Script
   ═══════════════════════════════════════════════════ */

"use strict";

(function () {
  /* ─── Backend API URL ─── */
  const API_BASE = "http://localhost:8000";

  /* ─── State ─── */
  const state = {
    currentView: "home",
    query: "",
    results: null,
    isStreaming: false,
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

    // Clear previous results
    resetResults();

    // Navigate to results view
    window.location.hash = "results";

    // Set query echo
    queryEchoText.textContent = query;

    // Show loading
    answerLoading.hidden = false;
    answerContent.hidden = true;
    sourcesSection.hidden = true;

    state.isStreaming = true;

    // Try backend API first, fall back to demo
    fetchAnswerFromBackend(query).then((result) => {
      if (result) {
        displayBackendResult(result);
      } else {
        // Fallback: use demo data
        setTimeout(() => {
          generateDemoAnswer(query);
        }, 800 + Math.random() * 600);
      }
      state.isStreaming = false;
    });
  }

  /* ─── Reset results ─── */
  function resetResults() {
    answerLoading.hidden = true;
    answerContent.hidden = true;
    sourcesSection.hidden = true;
    answerBody.innerHTML = "";
    sourceCards.innerHTML = "";
  }

  /* ─── Call the FastAPI backend ─── */
  async function fetchAnswerFromBackend(query) {
    try {
      const resp = await fetch(`${API_BASE}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
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
    answerLoading.hidden = true;
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
      if (sources.length > 0) {
        renderSourceCards(sources);
        updateMeta(sources);
      } else {
        sourcesSection.hidden = true;
      }
    });

    // Log provider info
    if (data.provider) {
      console.log(`Answered by: ${data.provider} · ${data.model}`);
    }
  }

  /* ─── Generate demo answer (fallback) ─── */
  function generateDemoAnswer(query) {
    const answerText = buildAnswer(query, demoSources);

    answerLoading.hidden = true;
    answerContent.hidden = false;

    streamAnswer(answerText, () => {
      renderSourceCards(demoSources);
      updateMeta(demoSources);
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

  /** Apply theme to the document */
  function applyTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
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

  /* ─── Init ─── */
  function init() {
    // Set footer year
    const footerYear = document.getElementById("footer-year");
    if (footerYear) footerYear.textContent = new Date().getFullYear();

    // ── Log active AI provider from config ──
    if (typeof AI_CONFIG !== "undefined") {
      console.log(
        `Active provider: ${AI_CONFIG.provider} · Model: ${getModelName() || "N/A"}`
      );
    }

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
