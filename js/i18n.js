/**
 * AI-Medikelizar — Internationalisation (i18n) System
 * ====================================================
 * Lightweight client-side i18n module with zero dependencies.
 *
 * Features:
 *   - Auto-detect browser language on first visit
 *   - Persist selection in localStorage
 *   - RTL-aware (sets dir, lang attributes on <html>)
 *   - __() function for dynamic translation with interpolation
 *   - translateDOM() for static content via data-i18n attributes
 *   - Extensible with locale config array for future languages
 */

(function () {
  "use strict";

  /* ─── Available Locales (extend by adding to this array) ─── */
  const LOCALES = [
    { code: "en", label: "English", nativeLabel: "English", dir: "ltr" },
    { code: "ar", label: "العربية", nativeLabel: "العربية", dir: "rtl" },
  ];

  const DEFAULT_LOCALE = "en";
  const STORAGE_KEY = "ai-medikelizar-locale";

  /* ─── State ─── */
  let currentLocale = DEFAULT_LOCALE;
  let currentDir = "ltr";
  let translations = {};
  let loadedLocales = {};

  /* ─── Detect best locale from browser ─── */
  function detectBrowserLocale() {
    const langs = navigator.languages || [navigator.language || ""];
    for (const lang of langs) {
      const code = lang.split("-")[0].toLowerCase();
      if (LOCALES.some((l) => l.code === code)) {
        return code;
      }
    }
    return DEFAULT_LOCALE;
  }

  /* ─── Load a locale file ─── */
  async function loadLocale(localeCode) {
    if (loadedLocales[localeCode]) {
      return loadedLocales[localeCode];
    }
    try {
      const resp = await fetch(`js/locales/${localeCode}.json`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      loadedLocales[localeCode] = data;
      return data;
    } catch (e) {
      console.warn(`i18n: Failed to load locale "${localeCode}" — falling back to en`, e.message);
      // Fall back to English
      if (localeCode !== "en" && !loadedLocales["en"]) {
        return loadLocale("en");
      }
      return loadedLocales["en"] || {};
    }
  }

  /* ─── Resolve a dotted key in a nested object ─── */
  function resolveKey(obj, key) {
    return key.split(".").reduce((acc, part) => {
      if (acc && typeof acc === "object" && part in acc) {
        return acc[part];
      }
      return undefined;
    }, obj);
  }

  /* ─── Translate a key with optional interpolation ─── */
  function __(key, params) {
    if (!key) return "";
    let value = resolveKey(translations, key);
    if (value === undefined || value === null) {
      // Fall back to key itself for missing translations
      return key;
    }
    if (typeof value === "object") {
      return value;
    }
    // Interpolate {param} placeholders
    if (params) {
      value = value.replace(/\{(\w+)\}/g, (_, p) => {
        return params[p] !== undefined ? params[p] : `{${p}}`;
      });
    }
    return value;
  }

  /* ─── Apply direction and lang to document ─── */
  function applyDirection(localeCode, dir) {
    document.documentElement.setAttribute("lang", localeCode);
    document.documentElement.setAttribute("dir", dir);
    currentDir = dir;
  }

  /* ─── Translate all static DOM elements with data-i18n ─── */
  function translateDOM() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const attr = el.getAttribute("data-i18n-attr");
      let value = __(key);

      // Handle array/object values (e.g. FAQ items, trust cards)
      if (typeof value === "object" && value !== null) {
        // For objects that need special handling, just use JSON for now
        value = JSON.stringify(value);
      }

      if (attr) {
        // Set a specific attribute (e.g. placeholder, aria-label)
        el.setAttribute(attr, value);
      } else {
        // Set inner HTML (allow safe HTML like <kbd>, <strong>)
        el.innerHTML = value;
      }
    });
  }

  /* ─── Get locale info by code ─── */
  function getLocaleInfo(code) {
    return LOCALES.find((l) => l.code === code) || LOCALES[0];
  }

  /* ─── Get all available locales ─── */
  function getAvailableLocales() {
    return LOCALES;
  }

  /* ─── Get current locale code ─── */
  function getCurrentLocale() {
    return currentLocale;
  }

  /* ─── Get current direction ─── */
  function getCurrentDir() {
    return currentDir;
  }

  /* ─── Set language ─── */
  async function setLanguage(localeCode) {
    if (!LOCALES.some((l) => l.code === localeCode)) {
      localeCode = DEFAULT_LOCALE;
    }
    const localeInfo = getLocaleInfo(localeCode);
    translations = await loadLocale(localeCode);
    currentLocale = localeCode;
    currentDir = localeInfo.dir;

    // Persist
    localStorage.setItem(STORAGE_KEY, localeCode);

    // Apply direction
    applyDirection(localeCode, localeInfo.dir);

    // Re-translate DOM
    translateDOM();

    // Dispatch a custom event so main.js can react
    document.dispatchEvent(new CustomEvent("localechange", {
      detail: { locale: localeCode, dir: localeInfo.dir, translations },
    }));
  }

  /* ─── Initialise i18n ─── */
  async function initI18n() {
    // Check for stored preference
    const stored = localStorage.getItem(STORAGE_KEY);
    const detected = detectBrowserLocale();
    const initialLocale = stored || detected || DEFAULT_LOCALE;

    const localeInfo = getLocaleInfo(initialLocale);

    // Load translations
    translations = await loadLocale(initialLocale);
    currentLocale = initialLocale;
    currentDir = localeInfo.dir;

    // Apply direction immediately (before DOM content loads)
    applyDirection(initialLocale, localeInfo.dir);
  }

  /* ─── Get locale list for language switcher ─── */
  function getLocales() {
    return LOCALES;
  }

  // ── Expose globally ──
  window.i18n = {
    __,
    translateDOM,
    setLanguage,
    getCurrentLocale,
    getCurrentDir,
    getAvailableLocales,
    getLocales,
    init: initI18n,
  };
})();
