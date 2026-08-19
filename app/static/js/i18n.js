<<<<<<< HEAD
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
=======
const i18nTranslations = {
    en: {
        dashboard: "Dashboard",
        societies: "Societies",
        buildings: "Buildings",
        flats: "Flats",
        residents: "Residents",
        maintenance: "Maintenance Billing",
        payments: "Payments & Dues",
        complaints: "Complaints Desk",
        visitors: "Visitor Management",
        parking: "Parking & Vehicles",
        facilities: "Facility Bookings",
        accounting: "Expenses & Ledger",
        documents: "Document Vault",
        reports: "Reports & Analytics",
        system: "System Health & Backups",
        logout: "Logout",
        pay_now: "Pay Dues Now",
        home: "Home",
        my_profile: "My Profile",
        my_bills: "My Bills",
        receipts: "Receipts",
        notifications: "Notifications",
        search: "Search",
        help_support: "Help & Support",
        more: "More",
        announcements: "Announcements",
        my_activity: "My Activity",
        documents: "Documents",
        support: "Support",
        preferences: "Preferences",
        contact_support: "Contact Support",
        create_request: "Create Request",
        subject: "Subject",
        category: "Category",
        message: "Message",
        submit: "Submit",
        status: "Status",
        status_open: "Open",
        status_in_progress: "In Progress",
        status_resolved: "Resolved",
        status_closed: "Closed",
        notification_preferences: "Notification Preferences",
        maintenance_reminders: "Maintenance Reminders",
        payment_reminders: "Payment Reminders",
        payment_confirmations: "Payment Confirmations",
        document_center: "Document Center",
        download: "Download",
        no_documents: "No documents yet",
        no_support_requests: "No support requests yet"
    },
    hi: {
        dashboard: "डैशबोर्ड",
        societies: "सोसाइटियां",
        buildings: "इमारतें",
        flats: "फ्लैट्स",
        residents: "निवासी",
        maintenance: "रखरखाव बिलिंग",
        payments: "भुगतान और बकाया",
        complaints: "शिकायत डेस्क",
        visitors: "आगंतुक प्रबंधन",
        parking: "पार्किंग और वाहन",
        facilities: "सुविधा बुकिंग",
        accounting: "खर्च और खाता",
        documents: "दस्तावेज़ तिजोरी",
        reports: "रिपोर्ट और विश्लेषिकी",
        system: "सिस्टम स्वास्थ्य और बैकअप",
        logout: "लॉग आउट",
        pay_now: "अभी भुगतान करें",
        home: "होम",
        my_profile: "मेरी प्रोफ़ाइल",
        my_bills: "मेरे बिल",
        receipts: "रसीदें",
        notifications: "सूचनाएं",
        search: "खोजें",
        help_support: "सहायता और समर्थन",
        more: "अधिक",
        announcements: "सूचनाएं",
        my_activity: "मेरी गतिविधि",
        documents: "दस्तावेज़",
        support: "सहायता",
        preferences: "प्राथमिकताएं",
        contact_support: "सहायता से संपर्क करें",
        create_request: "अनुरोध बनाएं",
        subject: "विषय",
        category: "श्रेणी",
        message: "संदेश",
        submit: "जमा करें",
        status: "स्थिति",
        status_open: "खुला",
        status_in_progress: "प्रगति में",
        status_resolved: "हल किया गया",
        status_closed: "बंद",
        notification_preferences: "सूचना प्राथमिकताएं",
        maintenance_reminders: "रखरखाव अनुस्मारक",
        payment_reminders: "भुगतान अनुस्मारक",
        payment_confirmations: "भुगतान पुष्टि",
        document_center: "दस्तावेज़ केंद्र",
        download: "डाउनलोड करें",
        no_documents: "अभी तक कोई दस्तावेज़ नहीं",
        no_support_requests: "अभी तक कोई सहायता अनुरोध नहीं"
    },
    gu: {
        dashboard: "ડેશબોર્ડ",
        societies: "સોસાયટીઓ",
        buildings: "ઈમારતો",
        flats: "ફ્લેટ્સ",
        residents: "રહેવાસીઓ",
        maintenance: "નિભાવ બિલિંગ",
        payments: "ચુકવણી અને બાકી",
        complaints: "ફરિયાદ ડેસ્ક",
        visitors: "મુલાકાતી વ્યવસ્થાપન",
        parking: "પાર્કિંગ અને વાહનો",
        facilities: "સુવિધા બુકિંગ",
        accounting: "ખર્ચ અને ખાતાવહી",
        documents: "દસ્તાવેજ વૉલ્ટ",
        reports: "રિપોર્ટ્સ અને એનાલિટિક્સ",
        system: "સિસ્ટમ હેલ્થ અને બેકઅપ",
        logout: "લૉગ આઉટ",
        pay_now: "હમણાં ચૂકવો",
        home: "હોમ",
        my_profile: "મારી પ્રોફાઇલ",
        my_bills: "મારા બિલ",
        receipts: "રસીદો",
        notifications: "સૂચનાઓ",
        search: "શોધો",
        help_support: "સહાય અને સપોર્ટ",
        more: "વધુ",
        announcements: "જાહેરાતો",
        my_activity: "મારી પ્રવૃત્તિ",
        documents: "દસ્તાવેજો",
        support: "સહાય",
        preferences: "પસંદગીઓ",
        contact_support: "સહાયનો સંપર્ક કરો",
        create_request: "વિનંતી બનાવો",
        subject: "વિષય",
        category: "શ્રેણી",
        message: "સંદેશ",
        submit: "સબમિટ કરો",
        status: "સ્થિતિ",
        status_open: "ખુલ્લું",
        status_in_progress: "પ્રગતિમાં",
        status_resolved: "ઉકેલાયેલ",
        status_closed: "બંધ",
        notification_preferences: "સૂચના પસંદગીઓ",
        maintenance_reminders: "જાળવણી રિમાઇન્ડર",
        payment_reminders: "ચુકવણી રિમાઇન્ડર",
        payment_confirmations: "ચુકવણી પુષ્ટિ",
        document_center: "દસ્તાવેજ કેન્દ્ર",
        download: "ડાઉનલોડ કરો",
        no_documents: "હજુ સુધી કોઈ દસ્તાવેજો નથી",
        no_support_requests: "હજુ સુધી કોઈ સહાય વિનંતીઓ નથી"
    }
};

function changeLanguage(lang) {
    if (!i18nTranslations[lang]) return;
    localStorage.setItem('app_lang', lang);
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (i18nTranslations[lang][key]) {
            el.textContent = i18nTranslations[lang][key];
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('app_lang') || 'en';
    changeLanguage(savedLang);
    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.value = savedLang;
        langSelect.addEventListener('change', (e) => changeLanguage(e.target.value));
    }
});
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
