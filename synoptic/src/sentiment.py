"""
sentiment.py
------------
A tiny, dependency-free lexicon-based sentiment scorer for social posts.

This intentionally avoids NLTK/TextBlob/VADER (all would require
`pip install`). It is not state-of-the-art, but it's transparent,
fast, and good enough to bucket posts into negative/neutral/positive
for a dashboard -- which is exactly what it's used for here.
"""

import re

POSITIVE_WORDS = {
    "safe", "calm", "clear", "sunny", "relief", "recovering", "recovered",
    "help", "helping", "helped", "thankful", "grateful", "great", "good",
    "beautiful", "lucky", "ok", "okay", "fine", "resilient", "strong",
    "together", "hope", "hopeful", "improving", "better", "rescued",
    "saved", "safe", "restored", "power's back", "sunshine",
}

NEGATIVE_WORDS = {
    "damage", "damaged", "destroyed", "destruction", "flood", "flooding",
    "flooded", "tornado", "hurricane", "storm", "danger", "dangerous",
    "warning", "emergency", "evacuate", "evacuation", "scared", "terrified",
    "afraid", "trapped", "stranded", "outage", "blackout", "power out",
    "no power", "dead", "died", "killed", "injured", "injury", "collapse",
    "collapsed", "wreck", "wrecked", "chaos", "panic", "worried", "worry",
    "loss", "lost", "devastating", "devastated", "severe", "extreme",
    "fear", "hail", "lightning", "wind damage", "roof gone", "help us",
}

NEGATION_WORDS = {"not", "no", "never", "n't", "without"}

_word_re = re.compile(r"[a-z']+")
_html_tag_re = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Mastodon post content is HTML; strip tags for plain-text analysis."""
    return _html_tag_re.sub(" ", text or "")


def score_text(text: str):
    """
    Return (label, score) where label is one of
    'positive' | 'neutral' | 'negative' and score is an integer
    (positive_hits - negative_hits).
    """
    clean = strip_html(text).lower()
    words = _word_re.findall(clean)

    pos_hits = 0
    neg_hits = 0
    for i, w in enumerate(words):
        preceded_by_negation = i > 0 and words[i - 1] in NEGATION_WORDS
        if w in POSITIVE_WORDS:
            if preceded_by_negation:
                neg_hits += 1
            else:
                pos_hits += 1
        elif w in NEGATIVE_WORDS:
            if preceded_by_negation:
                pos_hits += 1
            else:
                neg_hits += 1

    # multi-word phrases (simple substring check on top of word scoring)
    for phrase in ("power out", "no power", "power's back", "roof gone", "help us", "wind damage"):
        if phrase in clean:
            if phrase in ("power's back", "help us"):
                pos_hits += 1
            else:
                neg_hits += 1

    score = pos_hits - neg_hits
    if score > 0:
        label = "positive"
    elif score < 0:
        label = "negative"
    else:
        label = "neutral"
    return label, score
