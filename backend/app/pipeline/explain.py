"""
app/pipeline/explain.py — Multilingual reason text.

Returns reasons, next_steps, and field text in EN / HI / TA.
Uses a static lookup table — no runtime machine translation.
"""

from __future__ import annotations
from typing import Optional

# ── Translation table keyed by rule ID ────────────────────────────────────
# Each entry: { "en": str, "hi": str, "ta": str }

_RULE_TEXT: dict[str, dict[str, str]] = {
    "CODE_PRINT_MISMATCH": {
        "en": "The batch number or expiry date on the pack does not match the 2D code.",
        "hi": "पैक पर बैच नंबर या समाप्ति तिथि 2D कोड से मेल नहीं खाती।",
        "ta": "பேக்கில் உள்ள தொகுப்பு எண் அல்லது காலாவதி தேதி 2D குறியுடன் பொருந்தவில்லை.",
    },
    "GTIN_INVALID": {
        "en": "The product code has an invalid check digit.",
        "hi": "उत्पाद कोड में एक अमान्य चेक अंक है।",
        "ta": "தயாரிப்பு குறியீட்டில் தவறான சரிபார்ப்பு இலக்கம் உள்ளது.",
    },
    "EXPIRED": {
        "en": "This pack has passed its expiry date. Do not use.",
        "hi": "इस पैक की समाप्ति तिथि निकल चुकी है। उपयोग न करें।",
        "ta": "இந்த பேக்கின் காலாவதி தேதி கடந்துவிட்டது. பயன்படுத்த வேண்டாம்.",
    },
    "NAME_POSSIBLE_MISSPELLING": {
        "en": "The medicine name may have a spelling difference from the registered name.",
        "hi": "दवा के नाम में पंजीकृत नाम से वर्तनी का अंतर हो सकता है।",
        "ta": "மருந்தின் பெயரில் பதிவு செய்யப்பட்ட பெயரிலிருந்து உச்சரிப்பு வேறுபாடு இருக்கலாம்.",
    },
    "CODE_MISSING_FOR_LISTED_DRUG": {
        "en": "This medicine is in the database but no machine-readable code was found.",
        "hi": "यह दवा डेटाबेस में है लेकिन कोई मशीन-पठनीय कोड नहीं मिला।",
        "ta": "இந்த மருந்து தரவுத்தளத்தில் உள்ளது ஆனால் இயந்திரம் படிக்கக்கூடிய குறியீடு எதுவும் கிடைக்கவில்லை.",
    },
    "ALERT_EXACT": {
        "en": "This batch matches an official drug alert. Verify before use.",
        "hi": "यह बैच एक आधिकारिक दवा अलर्ट से मेल खाता है। उपयोग से पहले सत्यापित करें।",
        "ta": "இந்த தொகுப்பு அதிகாரப்பூர்வ மருந்து எச்சரிக்கையுடன் பொருந்துகிறது. பயன்படுத்துவதற்கு முன் சரிபார்க்கவும்.",
    },
    "ALERT_PARTIAL": {
        "en": "This batch partially matches a drug alert. Please confirm with your supplier.",
        "hi": "यह बैच आंशिक रूप से एक दवा अलर्ट से मेल खाता है। कृपया अपने आपूर्तिकर्ता से पुष्टि करें।",
        "ta": "இந்த தொகுப்பு ஒரு மருந்து எச்சரிக்கையுடன் பகுதியளவு பொருந்துகிறது. உங்கள் சப்ளையரிடம் உறுதிப்படுத்தவும்.",
    },
    "CLONE_STRONG": {
        "en": "Unusual scan activity for this code. Verify with the manufacturer before use.",
        "hi": "इस कोड के लिए असामान्य स्कैन गतिविधि। उपयोग से पहले निर्माता से सत्यापित करें।",
        "ta": "இந்த குறியீட்டிற்கு அசாதாரண ஸ்கேன் செயல்பாடு. பயன்படுத்துவதற்கு முன் உற்பத்தியாளரிடம் சரிபார்க்கவும்.",
    },
    "CLONE_MODERATE": {
        "en": "Unusual scan activity for this code. Verify with the manufacturer before use.",
        "hi": "इस कोड के लिए असामान्य स्कैन गतिविधि। उपयोग से पहले निर्माता से सत्यापित करें।",
        "ta": "இந்த குறியீட்டிற்கு அசாதாரண ஸ்கேன் செயல்பாடு. பயன்படுத்துவதற்கு முன் உற்பத்தியாளரிடம் சரிபார்க்கவும்.",
    },
    "REGISTRY_USED_OR_BLOCKED": {
        "en": "The serial number for this pack has already been scanned or is blocked.",
        "hi": "इस पैक का सीरियल नंबर पहले ही स्कैन किया जा चुका है या ब्लॉक है।",
        "ta": "இந்த பேக்கின் சீரியல் எண் ஏற்கனவே ஸ்கேன் செய்யப்பட்டது அல்லது தடுக்கப்பட்டுள்ளது.",
    },
    "LOW_VISUAL_SIMILARITY": {
        "en": "The pack looks different from the reference image for this medicine.",
        "hi": "पैक इस दवा की संदर्भ छवि से अलग दिखता है।",
        "ta": "இந்த மருந்தின் குறிப்பு படத்திலிருந்து பேக் வேறுபட்டு தெரிகிறது.",
    },
    "VISUAL_ANOMALY": {
        "en": "Unusual patterns detected in the pack image compared to the reference.",
        "hi": "पैक की छवि में संदर्भ की तुलना में असामान्य पैटर्न पाए गए।",
        "ta": "குறிப்பு படத்துடன் ஒப்பிடும்போது பேக் படத்தில் அசாதாரண வடிவங்கள் கண்டுபிடிக்கப்பட்டன.",
    },
    "LOW_OCR_CONFIDENCE": {
        "en": "Some text on the pack could not be read clearly.",
        "hi": "पैक पर कुछ टेक्स्ट स्पष्ट रूप से नहीं पढ़ा जा सका।",
        "ta": "பேக்கில் உள்ள சில உரை தெளிவாக படிக்க முடியவில்லை.",
    },
    "UNCLEAR_KEY_FIELDS": {
        "en": "Key fields such as batch or expiry could not be read with enough certainty.",
        "hi": "बैच या समाप्ति जैसे मुख्य फ़ील्ड पर्याप्त निश्चितता के साथ नहीं पढ़े जा सके।",
        "ta": "தொகுப்பு அல்லது காலாவதி போன்ற முக்கிய புலங்களை போதுமான நிச்சயத்துடன் படிக்க முடியவில்லை.",
    },
}

_NEXT_STEPS: dict[str, dict[str, list[str]]] = {
    "high_suspicion": {
        "en": [
            "Do not dispense or ingest this pack under any circumstance.",
            "Quarantine the pack in the designated suspicious-batch bin.",
            "Inform your upstream distributor immediately.",
            "File a report with your state drug regulatory authority.",
        ],
        "hi": [
            "किसी भी परिस्थिति में इस पैक को वितरित या उपयोग न करें।",
            "पैक को संदिग्ध बैच बिन में रखें।",
            "तत्काल अपने अपस्ट्रीम वितरक को सूचित करें।",
            "अपने राज्य दवा नियामक प्राधिकरण को रिपोर्ट करें।",
        ],
        "ta": [
            "எந்த சூழ்நிலையிலும் இந்த பேக்கை விநியோகிக்க அல்லது உட்கொள்ள வேண்டாம்.",
            "பேக்கை சந்தேகாஸ்பதமான தொகுப்பு தொட்டியில் வையுங்கள்.",
            "உங்கள் விநியோகஸ்தரை உடனடியாக தெரிவியுங்கள்.",
            "உங்கள் மாநில மருந்து ஒழுங்குமுறை ஆணையத்தில் புகார் அளியுங்கள்.",
        ],
    },
    "needs_verification": {
        "en": [
            "Check the batch number and expiry date against the purchase invoice.",
            "Ask your supplier for documentation for this batch.",
            "Set the pack aside and do not dispense until verified.",
        ],
        "hi": [
            "बैच नंबर और समाप्ति तिथि को खरीद चालान से जांचें।",
            "इस बैच के लिए अपने आपूर्तिकर्ता से दस्तावेज़ीकरण मांगें।",
            "पैक को अलग रखें और सत्यापित होने तक वितरित न करें।",
        ],
        "ta": [
            "கொள்முதல் ஆவணத்துடன் தொகுப்பு எண் மற்றும் காலாவதி தேதியை சரிபார்க்கவும்.",
            "இந்த தொகுப்பிற்கான ஆவணங்களை உங்கள் சப்ளையரிடம் கேளுங்கள்.",
            "பேக்கை தனியே வையுங்கள்; சரிபார்க்கும் வரை விநியோகிக்க வேண்டாம்.",
        ],
    },
    "low_risk": {
        "en": [
            "No inconsistencies found across all checks.",
            "Store as per label instructions.",
            "Report any concerns to your pharmacist supervisor.",
        ],
        "hi": [
            "सभी जांचों में कोई विसंगति नहीं पाई गई।",
            "लेबल निर्देशों के अनुसार स्टोर करें।",
            "किसी भी चिंता को अपने फार्मासिस्ट सुपरवाइज़र को रिपोर्ट करें।",
        ],
        "ta": [
            "அனைத்து சோதனைகளிலும் எந்த முரண்பாடும் இல்லை.",
            "லேபிள் வழிமுறைகளின்படி சேமியுங்கள்.",
            "ஏதேனும் கவலைகளை உங்கள் மருந்தாளுநர் மேற்பார்வையாளரிடம் தெரிவியுங்கள்.",
        ],
    },
    "insufficient_quality": {
        "en": [
            "Hold the camera steady and ensure good lighting.",
            "Avoid glare — tilt the pack slightly away from the light.",
            "Move closer to fill the frame with the medicine pack.",
        ],
        "hi": [
            "कैमरा स्थिर रखें और अच्छी रोशनी सुनिश्चित करें।",
            "चमक से बचें — पैक को हल्का झुकाएं।",
            "पैक के करीब आएं ताकि वह फ्रेम भर सके।",
        ],
        "ta": [
            "கேமராவை நிலையாக வைத்திருங்கள் மற்றும் நல்ல வெளிச்சம் உறுதிப்படுத்துங்கள்.",
            "பிரதிபலிப்பை தவிர்க்கவும் — பேக்கை சற்று சாய்க்கவும்.",
            "மருந்து பேக் கேமரா சட்டத்தை நிரப்பும் வரை நெருங்குங்கள்.",
        ],
    },
}


def localise_reasons(
    reasons: list[dict],
    language: str = "en",
) -> list[dict]:
    """Replace reason text with localised version if available."""
    lang = language if language in ("en", "hi", "ta") else "en"
    localised = []
    for r in reasons:
        rule_id = r.get("id", "")
        if rule_id in _RULE_TEXT:
            text = _RULE_TEXT[rule_id].get(lang, r["text"])
        else:
            text = r["text"]
        localised.append({**r, "text": text})
    return localised


def localise_next_steps(label: str, language: str = "en") -> list[str]:
    lang = language if language in ("en", "hi", "ta") else "en"
    return _NEXT_STEPS.get(label, {}).get(lang, _NEXT_STEPS.get(label, {}).get("en", []))
