"""
Communication Intelligence Services
===================================
Provides:
- Tone Checker (aggressive, vague, complicated, informal, confusing)
- Readability Checker (score, level, suggestions)
- Missing Information Detector (date, time, location, contact, action)
- Duplicate Announcement Detector (similarity matching against recent notices)
- Notice Simplifier ('Make Resident-Friendly': short, formal, simple)
- Translation Consistency Checker (cross-language completeness)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from app.models import Notice
from app.services.ai.provider import AIProviderFactory

logger = logging.getLogger(__name__)


class CommunicationAIService:
    """Authoritative Communication Intelligence Service."""

    # ── 1. Tone Checker ───────────────────────────────────────────────────────

    @classmethod
    def check_tone(cls, text: str) -> Dict[str, Any]:
        """
        Analyzes draft text and identifies tone flags:
        - Too aggressive
        - Too vague
        - Too complicated
        - Too informal
        - Confusing wording
        """
        if not text or not text.strip():
            return {
                "tone_score": 100,
                "overall_tone": "Neutral",
                "flags": [],
                "suggestions": ["Please enter text to analyze tone."],
            }

        t = text.strip()
        flags: List[Dict[str, str]] = []
        suggestions: List[str] = []

        # Check Aggressive Phrasing
        aggressive_patterns = [
            r"\bor else\b",
            r"\bstrictly forbidden\b",
            r"\bimmediate legal action\b",
            r"\bwill be seized\b",
            r"\bshut down immediately\b",
            r"\bpunishable\b",
            r"\bno excuses\b",
        ]
        found_agg = [p for p in aggressive_patterns if re.search(p, t, re.IGNORECASE)]
        has_all_caps = len(re.findall(r"\b[A-Z]{4,}\b", t)) >= 3

        if found_agg or has_all_caps:
            flags.append({
                "type": "too_aggressive",
                "severity": "warning",
                "description": "Phrasing may sound harsh or confrontational to residents.",
            })
            suggestions.append("Rephrase forceful warnings into polite, policy-focused reminders.")

        # Check Vague Phrasing
        vague_terms = ["sometime soon", "in due course", "at appropriate time", "as discussed", "etc."]
        found_vague = [v for v in vague_terms if v in t.lower()]
        if found_vague:
            flags.append({
                "type": "too_vague",
                "severity": "info",
                "description": f"Contains vague phrasing: '{', '.join(found_vague)}'.",
            })
            suggestions.append("Provide concrete dates, deadlines, or contact names.")

        # Check Complicated / Long Sentences
        sentences = [s.strip() for s in re.split(r"[.!?]+", t) if s.strip()]
        long_sentences = [s for s in sentences if len(s.split()) > 28]
        if long_sentences:
            flags.append({
                "type": "too_complicated",
                "severity": "info",
                "description": f"{len(long_sentences)} sentence(s) exceed 28 words.",
            })
            suggestions.append("Break down lengthy sentences into shorter, clear bullet points.")

        # Check Informal / Slang
        informal_words = ["hey guys", "btw", "asap", "fyi", "cool", "cheers", "plz", "thx"]
        found_inf = [w for w in informal_words if re.search(rf"\b{w}\b", t, re.IGNORECASE)]
        if found_inf:
            flags.append({
                "type": "too_informal",
                "severity": "info",
                "description": f"Contains casual slang: '{', '.join(found_inf)}'.",
            })
            suggestions.append("Use formal society communication standards for official announcements.")

        score = max(40, 100 - (len(flags) * 15))
        overall = "Professional & Balanced" if score >= 85 else ("Needs Minor Polishing" if score >= 70 else "Review Recommended")

        return {
            "tone_score": score,
            "overall_tone": overall,
            "flags": flags,
            "suggestions": suggestions or ["The text is well-balanced and professional."],
        }


    # ── 2. Readability Checker ─────────────────────────────────────────────────

    @classmethod
    def check_readability(cls, text: str) -> Dict[str, Any]:
        """
        Calculates readability metrics (Flesch score, level, suggestions).
        Return schema:
        {
            "score": 82,
            "level": "easy",
            "suggestions": [...]
        }
        """
        if not text or not text.strip():
            return {"score": 100, "level": "easy", "suggestions": []}

        words = re.findall(r"\b\w+\b", text)
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]

        num_words = max(len(words), 1)
        num_sentences = max(len(sentences), 1)

        # Approximate syllable count
        def count_syllables(word):
            word = word.lower()
            count = len(re.findall(r"[aeiouy]+", word))
            return max(1, count)

        total_syllables = sum(count_syllables(w) for w in words)

        # Flesch Reading Ease formula
        flesch_score = 206.835 - (1.015 * (num_words / num_sentences)) - (84.6 * (total_syllables / num_words))
        flesch_score = max(10, min(100, round(flesch_score, 1)))

        suggestions = []
        if flesch_score >= 80:
            level = "easy"
            suggestions.append("Very easy to read. Suitable for quick resident notifications.")
        elif flesch_score >= 60:
            level = "moderate"
            suggestions.append("Standard readability level. Clear for general society circulars.")
        else:
            level = "difficult"
            suggestions.append("Consider shortening sentences and simplifying complex terms.")

        if (num_words / num_sentences) > 22:
            suggestions.append("Average sentence length is high. Try splitting complex thoughts.")

        return {
            "score": int(flesch_score),
            "level": level,
            "word_count": num_words,
            "sentence_count": num_sentences,
            "avg_words_per_sentence": round(num_words / num_sentences, 1),
            "suggestions": suggestions,
        }

    # ── 3. Missing Information Detector ───────────────────────────────────────

    @classmethod
    def detect_missing_information(cls, text: str, notice_type: str = "General") -> Dict[str, Any]:
        """
        Checks for presence of essential notice components:
        - Date
        - Time
        - Location / Venue
        - Contact
        - Action Required
        """
        t = (text or "").lower()
        found_elements = {}
        missing_elements = []

        # Date detection
        has_date = bool(re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december))\b", t, re.IGNORECASE))
        has_date = has_date or any(w in t for w in ["today", "tomorrow", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"])
        found_elements["date"] = has_date

        # Time detection
        has_time = bool(re.search(r"\b(\d{1,2}(:\d{2})?\s*(am|pm|hrs|hours))\b", t, re.IGNORECASE))
        has_time = has_time or any(w in t for w in ["morning", "evening", "afternoon", "noon", "midnight"])
        found_elements["time"] = has_time

        # Location detection
        has_location = any(w in t for w in ["hall", "clubhouse", "gate", "garden", "wing", "block", "terrace", "lobby", "office", "premises", "venue", "society", "room"])
        found_elements["location"] = has_location

        # Contact detection
        has_contact = bool(re.search(r"\b\d{10}\b", t)) or any(w in t for w in ["contact", "call", "reach", "email", "manager", "security desk", "admin office"])
        found_elements["contact"] = has_contact

        # Action Required
        has_action = any(w in t for w in ["please", "requested", "must", "kindly", "submit", "pay", "attend", "register", "collect", "ensure", "avoid"])
        found_elements["action_required"] = has_action

        # Context-sensitive requirements
        if notice_type in ["Meeting", "AGM", "Event"]:
            if not has_date:
                missing_elements.append("Date of the meeting / event")
            if not has_time:
                missing_elements.append("Time of the meeting / event")
            if not has_location:
                missing_elements.append("Venue / Meeting location")
        elif notice_type in ["Maintenance", "Water", "Electricity"]:
            if not has_date:
                missing_elements.append("Date of maintenance work")
            if not has_time:
                missing_elements.append("Duration / Timings")
            if not has_contact:
                missing_elements.append("Contact person / technician number")

        return {
            "found_elements": found_elements,
            "missing_elements": missing_elements,
            "is_complete": len(missing_elements) == 0,
            "recommendation": (
                f"Consider adding: {', '.join(missing_elements)}."
                if missing_elements
                else "Notice contains all key logistical details."
            ),
        }

    # ── 4. Duplicate Announcement Detector ─────────────────────────────────────

    @classmethod
    def detect_duplicate_announcement(cls, society_id: int, draft_title: str, draft_content: str) -> Dict[str, Any]:
        """
        Compares draft announcement with recent society notices (last 90 days).
        Returns similarity percentage and matching notice details.
        """
        recent_notices = Notice.query.filter_by(society_id=society_id).order_by(
            Notice.created_at.desc()
        ).limit(20).all()

        if not recent_notices:
            return {"is_duplicate": False, "similarity_percentage": 0, "matching_notice": None}

        def tokenize(s):
            return set(re.findall(r"\b\w{3,}\b", (s or "").lower()))

        draft_tokens = tokenize(f"{draft_title} {draft_content}")
        if not draft_tokens:
            return {"is_duplicate": False, "similarity_percentage": 0, "matching_notice": None}

        highest_sim = 0.0
        best_match = None

        for n in recent_notices:
            n_tokens = tokenize(f"{n.title} {n.content}")
            if not n_tokens:
                continue

            # Jaccard similarity
            intersection = len(draft_tokens & n_tokens)
            union = len(draft_tokens | n_tokens)
            sim = (intersection / union) * 100 if union > 0 else 0.0

            if sim > highest_sim:
                highest_sim = sim
                best_match = n

        highest_sim_int = int(round(highest_sim))
        is_dup = highest_sim_int >= 65

        return {
            "is_duplicate": is_dup,
            "similarity_percentage": highest_sim_int,
            "matching_notice": {
                "id": best_match.id,
                "title": best_match.title,
                "created_at": best_match.created_at.strftime("%d %b %Y") if best_match.created_at else "Recent",
                "preview": best_match.content[:150] if best_match.content else "",
            } if best_match and highest_sim_int >= 40 else None,
            "warning": (
                f"Possible duplicate notice found ({highest_sim_int}% similarity with '{best_match.title}')."
                if is_dup and best_match
                else None
            ),
        }

    # ── 5. Notice Simplifier ('Make Resident-Friendly') ────────────────────────

    @classmethod
    def simplify_notice(cls, title: str, content: str) -> Dict[str, str]:
        """
        Generates 3 resident-friendly versions of a notice:
        - short: concise bullet points
        - formal: professional committee letter
        - simple: easy-to-read everyday language
        """
        provider = AIProviderFactory.get_provider()
        prompt = (
            f"Generate three versions of this society notice:\n"
            f"Title: {title}\n"
            f"Content: {content}\n\n"
            f"Respond with exact sections:\n"
            f"===SIMPLE===\n<friendly, plain English, no jargon>\n"
            f"===SHORT===\n<2-3 clear bullet points with key facts>\n"
            f"===FORMAL===\n<official managing committee circular>"
        )
        ai_resp = provider.generate(prompt, max_tokens=600, temperature=0.3)

        # Clean fallback versions
        simple_v = f"Dear Residents, please note the following update regarding {title.lower()}: {content}"
        short_v = f"• Update: {title}\n• Details: {content[:100]}...\n• For queries, contact Society Management."
        formal_v = f"CIRCULAR: {title.upper()}\n\nTo All Members & Residents,\n\n{content}\n\nBy Order,\nManaging Committee"

        if ai_resp and "===SIMPLE===" in ai_resp:
            try:
                parts = ai_resp.split("===")
                for idx, p in enumerate(parts):
                    if "SIMPLE" in p and idx + 1 < len(parts):
                        simple_v = parts[idx + 1].strip()
                    elif "SHORT" in p and idx + 1 < len(parts):
                        short_v = parts[idx + 1].strip()
                    elif "FORMAL" in p and idx + 1 < len(parts):
                        formal_v = parts[idx + 1].strip()
            except Exception:
                pass

        return {
            "original_title": title,
            "original_content": content,
            "simple_version": simple_v,
            "short_version": short_v,
            "formal_version": formal_v,
        }

    # ── 6. Translation Consistency Checker ─────────────────────────────────────

    @classmethod
    def check_translation_consistency(
        cls, original_english: str, translated_text: str, target_lang: str = "Hindi"
    ) -> Dict[str, Any]:
        """
        Compares multi-lingual translations with the original English text.
        Detects missing numbers, dates, times, or key instructions.
        """
        orig_nums = set(re.findall(r"\b\d+\b", original_english))
        trans_nums = set(re.findall(r"\b\d+\b", translated_text))
        missing_numbers = list(orig_nums - trans_nums)

        # Check relative sentence lengths
        orig_sentences = len([s for s in re.split(r"[.!?]+", original_english) if s.strip()])
        trans_sentences = len([s for s in re.split(r"[.!?।]+", translated_text) if s.strip()])
        sentence_disparity = abs(orig_sentences - trans_sentences) > 2

        issues: List[str] = []
        if missing_numbers:
            issues.append(f"Missing numbers/dates/amounts in translation: {', '.join(missing_numbers)}")
        if sentence_disparity:
            issues.append(f"Significant difference in sentence count ({orig_sentences} original vs {trans_sentences} translated).")

        return {
            "target_language": target_lang,
            "is_consistent": len(issues) == 0,
            "issues": issues,
            "missing_numbers": missing_numbers,
            "recommendation": (
                "Translation appears complete and consistent."
                if not issues
                else "Please verify that all dates, figures, and contact numbers match the original English notice."
            ),
        }
