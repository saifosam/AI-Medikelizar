/**
 * AI-Medikelizar — Internationalisation (i18n) System
 * ====================================================
 * Fully automatic language support for ANY language.
 *
 * Features:
 *   - Auto-detect ANY browser language on first visit (no hardcoded list)
 *   - Pass detected language directly to LLM for AI answers in ANY language
 *   - Static UI strings: try pre-built en/ar first, then LibreTranslate, then English fallback
 *   - RTL auto-detection from standard RTL language codes
 *   - Dynamic language switcher listing all major ISO 639-1 languages
 *   - Translations cached in localStorage to avoid repeated API calls
 *   - Persist selection in localStorage
 */

(function () {
  "use strict";

  /* ─── Standard RTL language codes (comprehensive, rarely changes) ─── */
  const RTL_LANGUAGES = new Set([
    "ar", "arc", "ckb", "dv", "fa", "ha", "he", "khw", "ks", "ku",
    "ps", "sd", "ug", "ur", "yi"
  ]);

  const DEFAULT_LOCALE = "en";
  const STORAGE_KEY = "ai-medikelizar-locale";
  const TRANS_CACHE_KEY = "ai-medikelizar-trans-cache";
  const TRANS_CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 days cache

  // LibreTranslate public endpoint (for UI string auto-translation)
  // Falls back gracefully if unavailable
  const LIBRE_TRANSLATE_URL = "https://translate.terraprint.co/translate";

  /* ─── State ─── */
  let currentLocale = DEFAULT_LOCALE;
  let currentDir = "ltr";
  let translations = {};
  let loadedLocales = {};

  /* ─── RTL detection by language code ─── */
  function isRtlLocale(code) {
    return RTL_LANGUAGES.has(code);
  }

  /* ─── Detect locale from browser (supports ANY language) ─── */
  function detectBrowserLocale() {
    const langs = navigator.languages || [navigator.language || ""];
    for (const lang of langs) {
      const code = lang.split("-")[0].toLowerCase();
      // Accept any ISO 639-1 code (2-3 letters), no hardcoded list
      if (/^[a-z]{2,3}$/.test(code)) {
        return code;
      }
    }
    return DEFAULT_LOCALE;
  }

  /* ─── Load a locale file (JSON first, then LibreTranslate, then en fallback) ─── */
  async function loadLocale(localeCode) {
    if (localeCode === "en") {
      // English is always loaded from file
      if (!loadedLocales["en"]) {
        try {
          const resp = await fetch("js/locales/en.json");
          if (resp.ok) {
            loadedLocales["en"] = await resp.json();
          }
        } catch (e) {
          console.warn("i18n: Could not load en.json", e.message);
        }
        if (!loadedLocales["en"]) loadedLocales["en"] = {};
      }
      return loadedLocales["en"];
    }

    if (loadedLocales[localeCode]) {
      return loadedLocales[localeCode];
    }

    // Try pre-built locale file first (en.json and ar.json exist)
    try {
      const resp = await fetch(`js/locales/${localeCode}.json`);
      if (resp.ok) {
        const data = await resp.json();
        loadedLocales[localeCode] = data;
        return data;
      }
    } catch (e) {
      // File doesn't exist — expected for unsupported languages
    }

    // No pre-built file — try LibreTranslate from English
    if (localeCode !== "en") {
      const translated = await translateViaLibre(localeCode);
      if (translated) {
        loadedLocales[localeCode] = translated;
        return translated;
      }
    }

    // Final fallback: English
    if (!loadedLocales["en"]) {
      await loadLocale("en");
    }
    return loadedLocales["en"] || {};
  }

  /* ─── Translate UI strings via LibreTranslate (cached) ─── */
  async function translateViaLibre(targetLang) {
    // Check cache first
    try {
      const cached = localStorage.getItem(TRANS_CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed[targetLang] && Date.now() - parsed[targetLang].ts < TRANS_CACHE_TTL) {
          return parsed[targetLang].data;
        }
      }
    } catch (e) { /* ignore cache errors */ }

    // Load English source strings
    if (!loadedLocales["en"]) {
      try {
        const resp = await fetch("js/locales/en.json");
        if (!resp.ok) return null;
        loadedLocales["en"] = await resp.json();
      } catch (e) {
        return null;
      }
    }

    const source = loadedLocales["en"];

    // Translate each top-level key
    const result = {};
    let successCount = 0;

    for (const [key, value] of Object.entries(source)) {
      if (typeof value === "string") {
        try {
          const resp = await fetch(LIBRE_TRANSLATE_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              q: value,
              source: "en",
              target: targetLang,
              format: "text",
            }),
            signal: AbortSignal.timeout(5000),
          });
          if (resp.ok) {
            const data = await resp.json();
            result[key] = data.translatedText || value;
            successCount++;
            // Small delay to avoid rate limiting
            if (successCount % 5 === 0) {
              await new Promise(r => setTimeout(r, 200));
            }
          } else {
            result[key] = value; // Fallback to English
          }
        } catch (e) {
          result[key] = value; // Fallback to English on error
        }
      } else if (typeof value === "object" && value !== null) {
        // For nested objects (like home.examples), keep as-is for now
        result[key] = value;
      } else {
        result[key] = value;
      }
    }

    // Cache the translation
    if (successCount > 0) {
      try {
        const cached = JSON.parse(localStorage.getItem(TRANS_CACHE_KEY) || "{}");
        cached[targetLang] = { data: result, ts: Date.now() };
        localStorage.setItem(TRANS_CACHE_KEY, JSON.stringify(cached));
      } catch (e) { /* ignore cache errors */ }
    }

    return successCount > 0 ? result : null;
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
      return key;
    }
    if (typeof value === "object") {
      return value;
    }
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

      if (typeof value === "object" && value !== null) {
        value = JSON.stringify(value);
      }

      if (attr) {
        el.setAttribute(attr, value);
      } else {
        el.innerHTML = value;
      }
    });
  }

  /* ─── Get current locale code ─── */
  function getCurrentLocale() {
    return currentLocale;
  }

  /* ─── Get current direction ─── */
  function getCurrentDir() {
    return currentDir;
  }

  /* ─── ISO 639-1 language name map (for dynamic dropdown) ─── */
  function getLanguageName(code) {
    const names = {
      en: "English", ar: "Arabic", zh: "Chinese", fr: "French", de: "German",
      hi: "Hindi", pt: "Portuguese", ru: "Russian", ja: "Japanese", es: "Spanish",
      it: "Italian", ko: "Korean", nl: "Dutch", pl: "Polish", tr: "Turkish",
      vi: "Vietnamese", th: "Thai", sv: "Swedish", da: "Danish", fi: "Finnish",
      nb: "Norwegian", cs: "Czech", hu: "Hungarian", ro: "Romanian", el: "Greek",
      he: "Hebrew", fa: "Persian", ur: "Urdu", id: "Indonesian", ms: "Malay",
      bn: "Bengali", ta: "Tamil", te: "Telugu", mr: "Marathi", gu: "Gujarati",
      kn: "Kannada", ml: "Malayalam", pa: "Punjabi", sw: "Swahili", tl: "Filipino",
      uk: "Ukrainian", sr: "Serbian", hr: "Croatian", bg: "Bulgarian", sk: "Slovak",
      sl: "Slovenian", lt: "Lithuanian", lv: "Latvian", et: "Estonian", ka: "Georgian",
      hy: "Armenian", az: "Azerbaijani", eu: "Basque", be: "Belarusian", bs: "Bosnian",
      ca: "Catalan", gl: "Galician", is: "Icelandic", mk: "Macedonian", mt: "Maltese",
      mn: "Mongolian", ne: "Nepali", si: "Sinhala", zu: "Zulu", af: "Afrikaans",
      am: "Amharic", ha: "Hausa", ig: "Igbo", jw: "Javanese", km: "Khmer",
      lo: "Lao", mi: "Maori", my: "Myanmar", ps: "Pashto", sd: "Sindhi",
      so: "Somali", su: "Sundanese", tg: "Tajik", uz: "Uzbek", cy: "Welsh",
      xh: "Xhosa", yi: "Yiddish", yo: "Yoruba"
    };
    return names[code] || code.toUpperCase();
  }

  /* ─── Get native name for a language ─── */
  function getNativeName(code) {
    try {
      const displayNames = new Intl.DisplayNames([code], { type: "language" });
      return displayNames.of(code) || getLanguageName(code);
    } catch (e) {
      return getLanguageName(code);
    }
  }

  /* ─── Set language ─── */
  async function setLanguage(localeCode) {
    if (!/^[a-z]{2,3}$/.test(localeCode)) {
      localeCode = DEFAULT_LOCALE;
    }
    const dir = isRtlLocale(localeCode) ? "rtl" : "ltr";
    translations = await loadLocale(localeCode);
    currentLocale = localeCode;
    currentDir = dir;

    localStorage.setItem(STORAGE_KEY, localeCode);
    applyDirection(localeCode, dir);
    translateDOM();

    document.dispatchEvent(new CustomEvent("localechange", {
      detail: { locale: localeCode, dir, translations },
    }));
  }

  /* ─── Initialise i18n ─── */
  async function initI18n() {
    const stored = localStorage.getItem(STORAGE_KEY);
    const detected = detectBrowserLocale();
    const initialLocale = stored || detected || DEFAULT_LOCALE;
    const dir = isRtlLocale(initialLocale) ? "rtl" : "ltr";

    translations = await loadLocale(initialLocale);
    currentLocale = initialLocale;
    currentDir = dir;

    applyDirection(initialLocale, dir);
  }

  /* ─── Get list of common languages for switcher ─── */
  function getCommonLanguages() {
    return [
      "en", "ar", "fr", "es", "pt", "de", "it", "ru", "zh", "ja",
      "ko", "hi", "bn", "ur", "fa", "tr", "nl", "pl", "sv", "da",
      "nb", "fi", "cs", "hu", "ro", "el", "he", "id", "ms", "th",
      "vi", "uk", "sr", "hr", "bg", "sk", "sl", "lt", "lv", "et",
      "ka", "hy", "az", "ca", "gl", "is", "mk", "mn", "ne", "si",
      "af", "am", "ha", "ig", "jw", "km", "lo", "my", "ps", "sd",
      "so", "su", "sw", "tl", "tg", "uz", "cy", "xh", "yi", "yo",
      "zu", "ta", "te", "mr", "gu", "kn", "ml", "pa"
    ];
  }

  /* ─── Get locale info (always returns valid data for ANY code) ─── */
  function getLocaleInfo(code) {
    const dir = isRtlLocale(code) ? "rtl" : "ltr";
    const label = getLanguageName(code);
    const nativeLabel = getNativeName(code);
    return { code, label, nativeLabel, dir };
  }

  // ── Expose globally ──
  window.i18n = {
    __,
    translateDOM,
    setLanguage,
    getCurrentLocale,
    getCurrentDir,
    getLocaleInfo,
    getCommonLanguages,
    getLanguageName,
    getNativeName,
    isRtlLocale,
    init: initI18n,
  };
})();
