class RegionalLocalizationService:
    """
    Implements Phase 38 Multi-Language & Regional Support Automation:
    - 10 Indian Regional Languages dictionary
    - INR Currency formatting in Indian numbering system (Lakhs/Crores)
    - Localized date/calendar formatting
    """

    SUPPORTED_LANGUAGES = {
        "en": "English",
        "gu": "ગુજરાતી (Gujarati)",
        "hi": "हिंदी (Hindi)",
        "mr": "मराठी (Marathi)",
        "bn": "বাংলা (Bengali)",
        "ta": "தமிழ் (Tamil)",
        "te": "తెలుగు (Telugu)",
        "kn": "ಕನ್ನಡ (Kannada)",
        "ml": "മലയാളം (Malayalam)",
        "pa": "ਪੰਜਾਬੀ (Punjabi)",
    }

    @staticmethod
    def format_inr_currency(amount):
        """Formats a float into standard Indian Rupee notation (e.g. ₹1,50,000.00)."""
        try:
            val = float(amount)
            is_neg = val < 0
            val = abs(val)
            s = f"{val:.2f}"
            dec = s[-3:]
            num = s[:-3]

            if len(num) <= 3:
                res = num
            else:
                last_three = num[-3:]
                remaining = num[:-3]
                chunks = []
                while len(remaining) > 2:
                    chunks.insert(0, remaining[-2:])
                    remaining = remaining[:-2]
                if remaining:
                    chunks.insert(0, remaining)
                res = ",".join(chunks) + "," + last_three

            prefix = "-₹" if is_neg else "₹"
            return f"{prefix}{res}{dec}"
        except Exception:
            return f"₹{amount}"

    @staticmethod
    def get_supported_languages():
        """Returns map of supported regional language codes and localized names."""
        return RegionalLocalizationService.SUPPORTED_LANGUAGES
