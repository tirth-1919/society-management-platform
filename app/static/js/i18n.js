// Centralized i18n Engine for Society SaaS Platform

function getCurrentLanguage() {
    return localStorage.getItem('app_lang') || 'en';
}

function t(key, fallback = '') {
    const lang = getCurrentLanguage();
    const translations = window.i18nTranslations || {};
    const dict = translations[lang] || translations['en'] || {};
    if (dict[key] !== undefined) {
        return dict[key];
    }
    // Fallback to English if available
    if (translations['en'] && translations['en'][key] !== undefined) {
        return translations['en'][key];
    }
    return fallback || key;
}

function translateElement(el, lang) {
    const translations = window.i18nTranslations || {};
    const dict = translations[lang] || translations['en'] || {};
    const defaultDict = translations['en'] || {};

    if (el.hasAttribute('data-i18n')) {
        const key = el.getAttribute('data-i18n');
        const translated = dict[key] !== undefined ? dict[key] : (defaultDict[key] || el.textContent);
        el.textContent = translated;
    }

    if (el.hasAttribute('data-i18n-placeholder')) {
        const key = el.getAttribute('data-i18n-placeholder');
        const translated = dict[key] !== undefined ? dict[key] : (defaultDict[key] || el.placeholder);
        el.placeholder = translated;
    }

    if (el.hasAttribute('data-i18n-title')) {
        const key = el.getAttribute('data-i18n-title');
        const translated = dict[key] !== undefined ? dict[key] : (defaultDict[key] || el.title);
        el.title = translated;
    }
}

function changeLanguage(lang) {
    const translations = window.i18nTranslations || {};
    if (!translations[lang]) {
        lang = 'en';
    }

    localStorage.setItem('app_lang', lang);
    document.cookie = `app_lang=${lang}; path=/; max-age=31536000; SameSite=Lax`;
    document.documentElement.lang = lang;

    // Update all static data-i18n elements in DOM
    document.querySelectorAll('[data-i18n], [data-i18n-placeholder], [data-i18n-title]').forEach(el => {
        translateElement(el, lang);
    });

    // Update language select if present
    const langSelect = document.getElementById('lang-select');
    if (langSelect && langSelect.value !== lang) {
        langSelect.value = lang;
    }

    // Dispatch event so active components, charts, and search dropdown re-render
    document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang } }));
}

// Auto-translate dynamically added DOM nodes
let isTranslating = false;
const observer = new MutationObserver((mutations) => {
    if (isTranslating) return;
    const currentLang = getCurrentLanguage();
    mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE) {
                isTranslating = true;
                if (node.hasAttribute('data-i18n') || node.hasAttribute('data-i18n-placeholder') || node.hasAttribute('data-i18n-title')) {
                    translateElement(node, currentLang);
                }
                node.querySelectorAll('[data-i18n], [data-i18n-placeholder], [data-i18n-title]').forEach(child => {
                    translateElement(child, currentLang);
                });
                isTranslating = false;
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const savedLang = getCurrentLanguage();
    changeLanguage(savedLang);

    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.value = savedLang;
        langSelect.addEventListener('change', (e) => {
            changeLanguage(e.target.value);
        });
    }

    observer.observe(document.body, { childList: true, subtree: true });
});

window.t = t;
window.changeLanguage = changeLanguage;
window.getCurrentLanguage = getCurrentLanguage;
