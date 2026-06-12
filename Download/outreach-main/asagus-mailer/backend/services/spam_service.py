"""
Spam score heuristic checker - pure Python, no external API.
Returns score 0-10 and list of triggered flags.
"""

import re
from typing import List, Dict, Any


def count_all_caps_words(text: str) -> int:
    """Count words that are all uppercase (more than 2 chars)."""
    return sum(1 for w in text.split() if w.isupper() and len(w) > 2)


def check_spam_phrases(subject: str, body: str) -> bool:
    """Check for known spam phrases in subject or body."""
    spam_phrases = [
        "click here", "buy now", "guaranteed", "winner", "you have been selected",
        "100% free", "earn money", "work from home", "make money fast",
        "no credit check", "cash bonus", "special offer", "limited offer",
        "order now", "call now", "don't delete", "you're a winner",
        "congratulations", "dear friend", "dear homeowner", "as seen on",
        "risk free", "lose weight", "be your own boss", "extra income",
        "fast cash", "no fees", "no investment", "no cost", "real money",
        "collect your prize", "claim your prize", "you have won",
    ]
    combined = (subject + " " + body).lower()
    return any(phrase in combined for phrase in spam_phrases)


SPAM_RULES = [
    ("ALL_CAPS_WORDS", 1.5, lambda s, b: count_all_caps_words(s + " " + b) > 3),
    ("EXCESSIVE_EXCLAMATION", 1.0, lambda s, b: (s + b).count("!") > 2),
    ("FREE_KEYWORD", 1.0, lambda s, b: "free" in (s + " " + b).lower()),
    ("URGENT_KEYWORD", 0.8, lambda s, b: any(
        w in (s + " " + b).lower()
        for w in ["urgent", "act now", "limited time", "expires today", "last chance"]
    )),
    ("MONEY_SYMBOLS", 1.2, lambda s, b: (s + b).count("$") + (s + b).count("€") > 1),
    ("NO_PERSONALIZATION", 1.5, lambda s, b: "{{name}}" not in b and "{{business}}" not in b),
    ("TOO_LONG", 0.5, lambda s, b: len(b.split()) > 200),
    ("MULTIPLE_LINKS", 1.0, lambda s, b: b.count("http") > 2),
    ("SPAM_PHRASES", 2.0, lambda s, b: check_spam_phrases(s, b)),
    ("MISSING_UNSUBSCRIBE", 1.5, lambda s, b: "{{unsubscribe_link}}" not in b and "unsubscribe" not in b.lower()),
    ("ALL_CAPS_SUBJECT", 1.5, lambda s, b: s.upper() == s and len(s) > 10),
    ("EXCESSIVE_PUNCTUATION", 0.8, lambda s, b: (s + b).count("???") > 0 or (s + b).count("!!!") > 0),
    ("SUSPICIOUS_WORDS", 1.2, lambda s, b: any(
        w in (s + " " + b).lower()
        for w in ["penis", "viagra", "cialis", "casino", "lottery", "prize", "million dollars"]
    )),
    ("NO_GREETING", 0.5, lambda s, b: not any(
        g in b.lower()[:100]
        for g in ["hi ", "hello ", "dear ", "hey ", "good morning", "good afternoon"]
    )),
]


def check_spam_score(subject: str, body: str) -> Dict[str, Any]:
    """
    Returns a spam score dict with score, is_safe flag, triggered flags, and recommendation.
    Score 0 = clean, 10+ = very likely spam.
    """
    triggered_flags = []
    total_score = 0.0

    for rule_name, weight, check_fn in SPAM_RULES:
        try:
            if check_fn(subject, body):
                triggered_flags.append({"rule": rule_name, "weight": weight})
                total_score += weight
        except Exception:
            pass

    total_score = round(min(total_score, 10.0), 2)
    is_safe = total_score < 5.0

    if total_score < 2.0:
        recommendation = "Excellent! Your email looks clean and well-personalized."
    elif total_score < 3.5:
        recommendation = "Good. Minor issues detected - consider reviewing flagged items."
    elif total_score < 5.0:
        recommendation = "Moderate spam risk. Address flagged items before sending."
    elif total_score < 7.0:
        recommendation = "High spam risk. Significant changes needed before sending."
    else:
        recommendation = "Very high spam risk. This email is likely to be blocked or junked."

    return {
        "score": total_score,
        "is_safe": is_safe,
        "flags": triggered_flags,
        "recommendation": recommendation,
    }
