"""Turn the free-text 'Publication info' line into a status + venue."""
import re

import venues

STATUS_ORDER = ["iacr", "iacr_revision", "elsewhere", "preprint", "other"]
STATUS_LABEL = {
    "iacr": "Published by the IACR",
    "iacr_revision": "Revision of an IACR publication",
    "elsewhere": "Published elsewhere",
    "preprint": "Preprint",
    "other": "Other",
}

IACR = re.compile(r"^Published by the IACR in\s+(.*?)\.?$", re.I)
IACR_REV = re.compile(r"^A (major|minor) revision of an IACR publication in\s+(.*?)\.?$", re.I)
ELSEWHERE = re.compile(r"^Published elsewhere\.?\s*(.*)$", re.I)
def _short(venue):
    """A groupable venue key: every spelling of ACM CCS folds onto 'ACM CCS'."""
    return venues.canonical(venue) or "Unspecified"


def classify(pubinfo):
    text = (pubinfo or "").strip()
    if not text:
        return {"status": "other", "venue": "", "venue_key": "Unspecified",
                "revision": ""}

    m = IACR.match(text)
    if m:
        venue = m.group(1).strip()
        return {"status": "iacr", "venue": venue, "venue_key": _short(venue),
                "revision": ""}

    m = IACR_REV.match(text)
    if m:
        venue = m.group(2).strip()
        return {"status": "iacr_revision", "venue": venue,
                "venue_key": _short(venue), "revision": m.group(1).lower()}

    m = ELSEWHERE.match(text)
    if m:
        rest = m.group(1).strip()
        rev = ""
        rm = re.match(r"^(Minor|Major) revision\.?\s*(.*)$", rest, re.I)
        if rm:
            rev, rest = rm.group(1).lower(), rm.group(2).strip()
        venue = re.sub(r"\s*DOI:\s*\S+\s*$", "", rest).strip().strip(".")
        return {"status": "elsewhere", "venue": venue,
                "venue_key": _short(venue) if venue else "Unspecified",
                "revision": rev}

    if re.match(r"^Preprint", text, re.I):
        rev = ""
        rm = re.search(r"(Minor|Major) revision", text, re.I)
        if rm:
            rev = rm.group(1).lower()
        return {"status": "preprint", "venue": "", "venue_key": "—",
                "revision": rev}

    return {"status": "other", "venue": text, "venue_key": _short(text),
            "revision": ""}
