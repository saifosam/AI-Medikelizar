/**
 * AI-Medikelizar — Automatic Currency System
 * ============================================
 * Detects user's currency from browser locale, fetches live exchange rates,
 * and converts EGP prices for display — zero manual configuration needed.
 *
 * Features:
 *   - Country detection from navigator.language (no API key needed)
 *   - Country → currency mapping (comprehensive, standard ISO data)
 *   - Live exchange rates via open.er-api.com (free, proxied through backend)
 *   - Smart rounding per currency conventions (JPY=no decimals, etc.)
 *   - Manual override persisted in localStorage
 *   - Graceful fallback to EGP on any error
 */

(function () {
  "use strict";

  const STORAGE_KEY = "ai-medikelizar-currency";
  const RATES_CACHE_KEY = "ai-medikelizar-rates-cache";
  const RATES_CACHE_TTL = 4 * 60 * 60 * 1000; // 4 hours

  /* ─── Country → Currency mapping (ISO 3166-1 alpha2 → ISO 4217) ─── */
  const COUNTRY_CURRENCY = {
    US: "USD", CA: "CAD", GB: "GBP", DE: "EUR", FR: "EUR", IT: "EUR",
    ES: "EUR", NL: "EUR", BE: "EUR", AT: "EUR", IE: "EUR", PT: "EUR",
    GR: "EUR", FI: "EUR", LU: "EUR", SK: "EUR", SI: "EUR", EE: "EUR",
    LV: "EUR", LT: "EUR", MT: "EUR", CY: "EUR", HR: "EUR", CH: "CHF",
    SE: "SEK", NO: "NOK", DK: "DKK", PL: "PLN", CZ: "CZK", HU: "HUF",
    RO: "RON", BG: "BGN", RS: "RSD", TR: "TRY", EG: "EGP", SA: "SAR",
    AE: "AED", QA: "QAR", KW: "KWD", BH: "BHD", OM: "OMR", JO: "JOD",
    LB: "LBP", IQ: "IQD", SY: "SYP", YE: "YER", PS: "ILS", IL: "ILS",
    JP: "JPY", CN: "CNY", HK: "HKD", TW: "TWD", KR: "KRW", SG: "SGD",
    MY: "MYR", TH: "THB", ID: "IDR", PH: "PHP", VN: "VND", IN: "INR",
    PK: "PKR", BD: "BDT", LK: "LKR", NP: "NPR", MM: "MMK", KH: "KHR",
    LA: "LAK", MN: "MNT", AU: "AUD", NZ: "NZD", RU: "RUB", UA: "UAH",
    BR: "BRL", MX: "MXN", AR: "ARS", CL: "CLP", CO: "COP", PE: "PEN",
    ZA: "ZAR", NG: "NGN", KE: "KES", TZ: "TZS", UG: "UGX", GH: "GHS",
    MA: "MAD", TN: "TND", DZ: "DZD", LY: "LYD", SD: "SDG", ET: "ETB",
    IC: "EUR", // Canary Islands
  };

  /* ─── Currency formatting rules ─── */
  const CURRENCY_FORMAT = {
    // Major currencies
    USD: { decimals: 2, symbol: "$", placement: "before" },
    EUR: { decimals: 2, symbol: "\u20ac", placement: "before" },  // €
    GBP: { decimals: 2, symbol: "\u00a3", placement: "before" },  // £
    CAD: { decimals: 2, symbol: "CA$", placement: "before" },
    AUD: { decimals: 2, symbol: "AU$", placement: "before" },
    CHF: { decimals: 2, symbol: "CHF ", placement: "before" },
    CNY: { decimals: 2, symbol: "\u00a5", placement: "before" },  // ¥
    JPY: { decimals: 0, symbol: "\u00a5", placement: "before" },  // ¥
    KRW: { decimals: 0, symbol: "\u20a9", placement: "before" },  // ₩
    VND: { decimals: 0, symbol: "\u20ab", placement: "after" },   // ₫
    CLP: { decimals: 0, symbol: "$", placement: "before" },
    COP: { decimals: 0, symbol: "$", placement: "before" },
    HUF: { decimals: 0, symbol: "Ft", placement: "after" },
    ISK: { decimals: 0, symbol: "kr", placement: "after" },
    TWD: { decimals: 0, symbol: "NT$", placement: "before" },
    IDR: { decimals: 0, symbol: "Rp", placement: "before" },
    KHR: { decimals: 0, symbol: "\u17db", placement: "before" },
    LAK: { decimals: 0, symbol: "\u20ad", placement: "before" },
    MNT: { decimals: 0, symbol: "\u20ae", placement: "before" },
    MMR: { decimals: 0, symbol: "K", placement: "before" },
    IQD: { decimals: 3, symbol: "\u0639.\u062f", placement: "before" },
    KWD: { decimals: 3, symbol: "\u062f.\u0643", placement: "before" },
    OMR: { decimals: 3, symbol: "\u0631.\u0639.", placement: "before" },
    BHD: { decimals: 3, symbol: "\u062f.\u0628", placement: "before" },
    SAR: { decimals: 2, symbol: "\u0631.\u0633", placement: "before" },  // ر.س
    AED: { decimals: 2, symbol: "\u062f.\u0625", placement: "before" },  // د.إ
    QAR: { decimals: 2, symbol: "\u0631.\u0642", placement: "before" },  // ر.ق
    TRY: { decimals: 2, symbol: "\u20a4", placement: "before" },  // ₺
    RUB: { decimals: 2, symbol: "\u20bd", placement: "before" },  // ₽
    BRL: { decimals: 2, symbol: "R$", placement: "before" },
    INR: { decimals: 2, symbol: "\u20b9", placement: "before" },  // ₹
    SEK: { decimals: 2, symbol: "kr", placement: "after" },
    NOK: { decimals: 2, symbol: "kr", placement: "after" },
    DKK: { decimals: 2, symbol: "kr", placement: "after" },
    PLN: { decimals: 2, symbol: "z\u0142", placement: "after" },  // zł
    ZAR: { decimals: 2, symbol: "R", placement: "before" },
    MAD: { decimals: 2, symbol: "\u062f.\u0645.", placement: "before" },  // د.م.
    EGP: { decimals: 2, symbol: "EGP ", placement: "before" },
    NZD: { decimals: 2, symbol: "NZ$", placement: "before" },
    SGD: { decimals: 2, symbol: "S$", placement: "before" },
    HKD: { decimals: 2, symbol: "HK$", placement: "before" },
    MYR: { decimals: 2, symbol: "RM", placement: "before" },
    THB: { decimals: 2, symbol: "\u0e3f", placement: "before" },  // ฿
    PHP: { decimals: 2, symbol: "\u20b1", placement: "before" },  // ₱
    // Default: 2 decimal places
  };

  const DEFAULT_FORMAT = { decimals: 2, symbol: "EGP", placement: "before" };

  /* ─── State ─── */
  let currentCurrency = "EGP";
  let exchangeRates = { EGP: 1 };
  let ratesLoaded = false;

  /* ─── Detect country from browser locale ─── */
  function detectCountry() {
    try {
      const lang = navigator.language || "";
      const parts = lang.split("-");
      if (parts.length >= 2 && parts[1].length === 2) {
        const region = parts[1].toUpperCase();
        if (COUNTRY_CURRENCY[region]) {
          return region;
        }
      }
      // Try Intl.DateTimeFormat as fallback
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz && tz.includes("/")) {
        const region = tz.split("/")[1];
        // Try to match known mappings
        const regionMapping = {
          Cairo: "EG", Dubai: "AE", Riyadh: "SA", Kuwait: "KW",
          London: "GB", Paris: "FR", Berlin: "DE", Tokyo: "JP",
          Shanghai: "CN", Hong_Kong: "HK", Seoul: "KR",
          New_York: "US", Chicago: "US", Los_Angeles: "US",
          Sydney: "AU", Delhi: "IN", Mumbai: "IN", Singapore: "SG",
          Moscow: "RU", Sao_Paulo: "BR", Istanbul: "TR",
        };
        if (regionMapping[region]) {
          return regionMapping[region];
        }
      }
    } catch (e) {
      // ignore
    }
    return null;
  }

  /* ─── Detect currency from browser ─── */
  function detectCurrency() {
    const country = detectCountry();
    if (country && COUNTRY_CURRENCY[country]) {
      return COUNTRY_CURRENCY[country];
    }
    return "EGP"; // Default to base currency
  }

  /* ─── Fetch exchange rates from backend (proxies open.er-api.com) ─── */
  async function fetchRates() {
    // Try localStorage cache first
    try {
      const cached = localStorage.getItem(RATES_CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Date.now() - parsed.ts < RATES_CACHE_TTL) {
          exchangeRates = parsed.rates;
          ratesLoaded = true;
          return parsed.rates;
        }
      }
    } catch (e) { /* ignore */ }

    const API_BASE = (
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      window.location.hostname === ""
    ) ? "http://localhost:8000" : "";

    try {
      const resp = await fetch(`${API_BASE}/api/currency/rates`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.result === "success" && data.rates) {
          exchangeRates = data.rates;
          ratesLoaded = true;
          // Cache in localStorage
          try {
            localStorage.setItem(RATES_CACHE_KEY, JSON.stringify({
              rates: data.rates,
              ts: Date.now(),
            }));
          } catch (e) { /* ignore */ }
          return data.rates;
        }
      }
    } catch (e) {
      console.warn("Currency: Failed to fetch rates:", e.message);
    }

    // Fallback: use cache even if stale
    try {
      const cached = localStorage.getItem(RATES_CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        exchangeRates = parsed.rates;
        ratesLoaded = true;
        return parsed.rates;
      }
    } catch (e) { /* ignore */ }

    return { EGP: 1 };
  }

  /* ─── Convert EGP amount to target currency ─── */
  function convertPrice(priceCents, toCurrency) {
    const amountEGP = priceCents / 100;
    const rate = exchangeRates[toCurrency];
    if (!rate || rate <= 0) return amountEGP;
    return amountEGP * rate;
  }

  /* ─── Format price for display ─── */
  function formatPrice(amount, currency) {
    const fmt = CURRENCY_FORMAT[currency] || DEFAULT_FORMAT;
    const rounded = fmt.decimals === 0
      ? Math.round(amount)
      : Number(amount.toFixed(fmt.decimals));

    const formatted = rounded.toLocaleString(
      currency === "EGP" ? "en-US" : undefined,
      { minimumFractionDigits: fmt.decimals, maximumFractionDigits: fmt.decimals }
    );

    if (fmt.placement === "after") {
      return `${formatted} ${fmt.symbol}`;
    }
    return `${fmt.symbol}${formatted}`;
  }

  /* ─── Format EGP price cents in detected currency ─── */
  function formatPriceCents(priceCents, currency) {
    const amount = convertPrice(priceCents, currency);
    return formatPrice(amount, currency);
  }

  /* ─── Get user's current currency ─── */
  function getCurrentCurrency() {
    return currentCurrency;
  }

  /* ─── Get exchange rate for a currency ─── */
  function getRate(currency) {
    return exchangeRates[currency] || 1;
  }

  /* ─── Set manual currency override ─── */
  function setCurrency(code) {
    currentCurrency = code;
    localStorage.setItem(STORAGE_KEY, code);
    document.dispatchEvent(new CustomEvent("currencychange", {
      detail: { currency: code },
    }));
  }

  /* ─── Initialise currency system ─── */
  async function initCurrency() {
    const stored = localStorage.getItem(STORAGE_KEY);
    const detected = detectCurrency();
    currentCurrency = stored || detected || "EGP";
    await fetchRates();
  }

  /* ─── Get list of common currencies for override dropdown ─── */
  function getCommonCurrencies() {
    return [
      { code: "EGP", name: "Egyptian Pound" },
      { code: "USD", name: "US Dollar" },
      { code: "EUR", name: "Euro" },
      { code: "GBP", name: "British Pound" },
      { code: "SAR", name: "Saudi Riyal" },
      { code: "AED", name: "UAE Dirham" },
      { code: "KWD", name: "Kuwaiti Dinar" },
      { code: "QAR", name: "Qatari Riyal" },
      { code: "JPY", name: "Japanese Yen" },
      { code: "CNY", name: "Chinese Yuan" },
      { code: "INR", name: "Indian Rupee" },
      { code: "CAD", name: "Canadian Dollar" },
      { code: "AUD", name: "Australian Dollar" },
      { code: "CHF", name: "Swiss Franc" },
      { code: "TRY", name: "Turkish Lira" },
      { code: "RUB", name: "Russian Ruble" },
      { code: "BRL", name: "Brazilian Real" },
      { code: "ZAR", name: "South African Rand" },
      { code: "MAD", name: "Moroccan Dirham" },
      { code: "NOK", name: "Norwegian Krone" },
      { code: "SEK", name: "Swedish Krona" },
      { code: "DKK", name: "Danish Krone" },
    ];
  }

  /* ─── Check if rates have been loaded ─── */
  function isRatesLoaded() {
    return ratesLoaded;
  }

  // ── Expose globally ──
  window.AICurrency = {
    init: initCurrency,
    detectCurrency,
    detectCountry,
    fetchRates,
    convertPrice,
    formatPrice,
    formatPriceCents,
    getCurrentCurrency,
    getRate,
    setCurrency,
    getCommonCurrencies,
    isRatesLoaded,
    COUNTRY_CURRENCY,
  };
})();
