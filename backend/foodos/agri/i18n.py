"""Localisation — Hindi first, English as the fallback, room for the rest.

**Hindi is the default, not an option bolted on afterwards.** The primary user is
an FPO manager or an aggregator at a collection hub, and the product's own design
rule is that they get one number on WhatsApp. A number in a language they read
second is a number they act on second.

So `Locale.HI` is the default argument everywhere, English is the fallback, and
an untranslated key surfaces as a test failure rather than as silent English
leaking into a Hindi message.

Three things this module refuses to do the easy way.

**Terminology is agricultural, not literal.** Hindi distinguishes कटाई (cutting,
what you do to wheat) from तुड़ाई (plucking, what you do to a tomato). A
translation table that renders "harvest" as कटाई throughout is grammatically fine
and marks you instantly as someone who has never stood in a field. Same for बोरी
(the gunny sack that actually exists in the trade) over a transliterated "gunny
bag", and मंडी over "wholesale market".

**Numbers group the Indian way.** 153000 is written 1,53,000 — thousand, then
lakh, then crore — not 153,000. Every rupee and kilogram figure in this product
is read by someone who groups in lakhs, and Western grouping makes a number look
wrong before it is read. `format_indian()` handles it.

**Coverage is honest per locale.** Hindi and English are complete and reviewed.
Kannada and Marathi are present because the pilot corridors are Karnataka and
Maharashtra, and are marked `needs_native_review` — they fall back key-by-key
rather than shipping a confident half-translation. A gap that degrades to Hindi
is recoverable; a wrong word in front of a mandi trader is not.

Numerals stay Latin. Devanagari digits (१२३) are readable but nobody in Indian
agricultural trade writes prices in them, and a price is for acting on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Locale(StrEnum):
    HI = "hi"  # हिन्दी — default
    EN = "en"  # fallback and source of truth
    KN = "kn"  # ಕನ್ನಡ — Karnataka pilot
    MR = "mr"  # मराठी — Maharashtra pilot


DEFAULT_LOCALE = Locale.HI

#: Fallback order. A missing Hindi key is a bug; a missing Kannada key is a
#: known gap that degrades to Hindi and then to English rather than to nothing.
FALLBACK_CHAIN: dict[Locale, tuple[Locale, ...]] = {
    Locale.HI: (Locale.EN,),
    Locale.EN: (),
    Locale.KN: (Locale.HI, Locale.EN),
    Locale.MR: (Locale.HI, Locale.EN),
}


@dataclass(frozen=True)
class LocaleInfo:
    code: Locale
    endonym: str
    script: str
    #: Whether a native speaker with trade vocabulary has signed this off. False
    #: means usable but not demo-safe without a review pass — stated rather than
    #: quietly assumed.
    native_reviewed: bool


LOCALES: dict[Locale, LocaleInfo] = {
    Locale.HI: LocaleInfo(Locale.HI, "हिन्दी", "Devanagari", True),
    Locale.EN: LocaleInfo(Locale.EN, "English", "Latin", True),
    Locale.KN: LocaleInfo(Locale.KN, "ಕನ್ನಡ", "Kannada", False),
    Locale.MR: LocaleInfo(Locale.MR, "मराठी", "Devanagari", False),
}


# --------------------------------------------------------------------------
# Indian number formatting
# --------------------------------------------------------------------------


def format_indian(value: float, decimals: int = 0) -> str:
    """Group digits the Indian way: 1,53,000 rather than 153,000.

    The last three digits group together, then every two after that — thousand,
    lakh, crore. Getting this wrong is not cosmetic: a reader who groups in
    lakhs sees 153,000 and has to stop and re-parse, and a number that has to be
    re-parsed is a number that loses an argument.
    """
    negative = value < 0
    whole = abs(float(value))
    fraction = ""
    if decimals > 0:
        fraction = f"{whole - int(whole):.{decimals}f}"[1:]
    digits = str(int(whole))

    if len(digits) <= 3:
        grouped = digits
    else:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join([*parts, tail])

    return ("-" if negative else "") + grouped + fraction


def format_kg(value: float, locale: Locale = DEFAULT_LOCALE) -> str:
    return f"{format_indian(value, 0 if abs(value) >= 10 else 1)} {t('unit.kg', locale)}"


def format_hours(value: float, locale: Locale = DEFAULT_LOCALE) -> str:
    return f"{format_indian(value, 1)} {t('unit.hours', locale)}"


def format_pct(value: float, locale: Locale = DEFAULT_LOCALE) -> str:
    return f"{value:.1f}{t('unit.percent', locale)}"


# --------------------------------------------------------------------------
# Strings
# --------------------------------------------------------------------------

# Keys are namespaced by what they label, so a missing one is obvious in a diff.
# English is the source of truth; Hindi is the shipped default.
STRINGS: dict[str, dict[Locale, str]] = {
    # --- units -------------------------------------------------------------
    "unit.kg": {Locale.EN: "kg", Locale.HI: "किलो", Locale.KN: "ಕೆ.ಜಿ.", Locale.MR: "किलो"},
    "unit.hours": {Locale.EN: "hours", Locale.HI: "घंटे", Locale.KN: "ಗಂಟೆ", Locale.MR: "तास"},
    "unit.percent": {Locale.EN: "%", Locale.HI: "%", Locale.KN: "%", Locale.MR: "%"},
    "unit.rupees": {Locale.EN: "Rs", Locale.HI: "रु", Locale.KN: "ರೂ", Locale.MR: "रु"},
    "unit.celsius": {Locale.EN: "C", Locale.HI: "से", Locale.KN: "ಸೆ", Locale.MR: "से"},
    # --- commodities -------------------------------------------------------
    "commodity.tomato": {
        Locale.EN: "Tomato", Locale.HI: "टमाटर",
        Locale.KN: "ಟೊಮ್ಯಾಟೊ", Locale.MR: "टोमॅटो",
    },
    "commodity.potato": {
        Locale.EN: "Potato", Locale.HI: "आलू",
        Locale.KN: "ಆಲೂಗಡ್ಡೆ", Locale.MR: "बटाटा",
    },
    "commodity.guava": {
        Locale.EN: "Guava", Locale.HI: "अमरूद",
        Locale.KN: "ಸೀಬೆಕಾಯಿ", Locale.MR: "पेरू",
    },
    # --- questionnaire field labels ---------------------------------------
    # तुड़ाई, not कटाई. कटाई is cutting a grain crop; तुड़ाई is plucking a fruit
    # or vegetable, which is what actually happens to a tomato.
    "field.harvest_method": {
        Locale.EN: "Harvest method", Locale.HI: "तुड़ाई का तरीका",
        Locale.KN: "ಕೊಯ್ಲು ವಿಧಾನ", Locale.MR: "काढणीची पद्धत",
    },
    "field.harvest_window": {
        Locale.EN: "Harvest time", Locale.HI: "तुड़ाई का समय",
        Locale.KN: "ಕೊಯ್ಲು ಸಮಯ", Locale.MR: "काढणीची वेळ",
    },
    "field.field_holding": {
        Locale.EN: "Where it was kept in the field", Locale.HI: "खेत में कहाँ रखा",
        Locale.MR: "शेतात कुठे ठेवले",
    },
    "field.field_hours": {
        Locale.EN: "Hours kept in the field", Locale.HI: "खेत में कितने घंटे रखा",
        Locale.MR: "शेतात किती तास ठेवले",
    },
    "field.packaging": {
        Locale.EN: "Packaging", Locale.HI: "पैकिंग",
        Locale.KN: "ಪ್ಯಾಕಿಂಗ್", Locale.MR: "पॅकिंग",
    },
    "field.transport_mode": {
        Locale.EN: "Vehicle type", Locale.HI: "गाड़ी का प्रकार",
        Locale.KN: "ವಾಹನದ ಪ್ರಕಾರ", Locale.MR: "वाहनाचा प्रकार",
    },
    "field.transit_hours": {
        Locale.EN: "Hours on the road", Locale.HI: "रास्ते के घंटे",
        Locale.MR: "रस्त्यावरील तास",
    },
    "field.mandi_holding_hours": {
        Locale.EN: "Hours waiting at the mandi", Locale.HI: "मंडी में इंतज़ार के घंटे",
        Locale.MR: "मंडईत थांबण्याचे तास",
    },
    "field.maturity_factor": {
        Locale.EN: "Ripeness at harvest", Locale.HI: "तुड़ाई के समय पकाव",
        Locale.MR: "काढणीच्या वेळी पक्वता",
    },
    "field.visual_damage_fraction": {
        Locale.EN: "Visible damage", Locale.HI: "दिखने वाला नुकसान",
        Locale.MR: "दिसणारे नुकसान",
    },
    "field.ambient_mean_c": {
        Locale.EN: "Outside temperature", Locale.HI: "बाहर का तापमान",
        Locale.MR: "बाहेरचे तापमान",
    },
    # This one was missing, and its absence was not harmless. `sensitivity()`
    # can name any uncertain field as the biggest unknown, so a missing label
    # made `predict()` raise — and the caller upstream wraps it in a broad
    # `except Exception` that degrades to a row with no interval but *unchanged*
    # confidence. A loud failure became a quietly confident wrong number.
    # `test_every_field_the_engine_can_name_has_a_label` closes the class.
    "field.diurnal_amplitude_c": {
        Locale.EN: "Day-night temperature swing",
        Locale.HI: "दिन-रात के तापमान में फर्क",
        Locale.MR: "दिवस-रात्र तापमानातील फरक",
    },
    "field.road_roughness": {
        Locale.EN: "Road condition", Locale.HI: "सड़क की हालत",
        Locale.MR: "रस्त्याची स्थिती",
    },
    "field.quantity_kg": {
        Locale.EN: "Quantity", Locale.HI: "मात्रा", Locale.MR: "प्रमाण",
    },
    # --- questionnaire options --------------------------------------------
    "opt.manual": {Locale.EN: "By hand", Locale.HI: "हाथ से", Locale.MR: "हाताने"},
    "opt.mechanical": {Locale.EN: "By machine", Locale.HI: "मशीन से", Locale.MR: "मशीनने"},
    "opt.pre_dawn": {Locale.EN: "Before dawn", Locale.HI: "तड़के", Locale.MR: "पहाटे"},
    "opt.morning": {Locale.EN: "Morning", Locale.HI: "सुबह", Locale.MR: "सकाळी"},
    "opt.midday": {Locale.EN: "Midday", Locale.HI: "दोपहर", Locale.MR: "दुपारी"},
    "opt.afternoon": {
        Locale.EN: "Late afternoon", Locale.HI: "दोपहर बाद", Locale.MR: "दुपारनंतर",
    },
    # The questionnaire's shade vocabulary is finer-grained than the engine's
    # three-way enum, so its values are translated here too. Anything still
    # unlisted degrades through `humanise()` rather than raising.
    "opt.immediate": {
        Locale.EN: "Yes, straight away", Locale.HI: "हाँ, तुरंत",
        Locale.MR: "होय, लगेच",
    },
    "opt.partial": {
        Locale.EN: "Partly shaded", Locale.HI: "कुछ हद तक छाया में",
        Locale.MR: "अंशतः सावलीत",
    },
    "opt.early_morning": {
        Locale.EN: "Early morning", Locale.HI: "सुबह जल्दी", Locale.MR: "पहाटे लवकर",
    },
    "opt.open_sun": {Locale.EN: "In the open sun", Locale.HI: "खुली धूप में", Locale.MR: "उन्हात"},
    "opt.shade": {Locale.EN: "In shade", Locale.HI: "छाया में", Locale.MR: "सावलीत"},
    "opt.cold_room": {Locale.EN: "In a cold room", Locale.HI: "कोल्ड रूम में", Locale.MR: "कोल्ड रूममध्ये"},
    # बोरी is the sack the trade actually uses. "Gunny bag" transliterated would
    # be understood by nobody who handles one.
    "opt.gunny_bag": {Locale.EN: "Gunny sack", Locale.HI: "बोरी", Locale.MR: "पोते"},
    "opt.loose_bulk": {
        Locale.EN: "Loose in bulk", Locale.HI: "खुला भरा हुआ", Locale.MR: "सुटे भरलेले",
    },
    "opt.wooden_crate": {
        Locale.EN: "Wooden crate", Locale.HI: "लकड़ी की पेटी", Locale.MR: "लाकडी खोका",
    },
    "opt.ventilated_plastic_crate": {
        Locale.EN: "Ventilated plastic crate", Locale.HI: "हवादार प्लास्टिक क्रेट",
        Locale.MR: "हवेशीर प्लास्टिक क्रेट",
    },
    "opt.open_truck": {Locale.EN: "Open truck", Locale.HI: "खुला ट्रक", Locale.MR: "उघडा ट्रक"},
    "opt.tarpaulin": {
        Locale.EN: "Covered with tarpaulin", Locale.HI: "तिरपाल से ढका",
        Locale.MR: "ताडपत्रीने झाकलेले",
    },
    "opt.refrigerated": {
        Locale.EN: "Refrigerated vehicle", Locale.HI: "शीतित (रेफ्रिजरेटेड) गाड़ी",
        Locale.MR: "शीतित वाहन",
    },
    # --- output labels ----------------------------------------------------
    "out.loss": {Locale.EN: "Expected loss", Locale.HI: "अनुमानित नुकसान",
                 Locale.KN: "ನಿರೀಕ್ಷಿತ ನಷ್ಟ", Locale.MR: "अपेक्षित नुकसान"},
    "out.at_risk": {Locale.EN: "At risk", Locale.HI: "खतरे में", Locale.MR: "धोक्यात"},
    "out.rul": {
        Locale.EN: "Time left before it stops selling fresh",
        Locale.HI: "ताज़ा बिकने का बाकी समय",
        Locale.MR: "ताजे विकण्यासाठी उरलेला वेळ",
    },
    "out.rul_short": {Locale.EN: "Time left", Locale.HI: "बाकी समय", Locale.MR: "उरलेला वेळ"},
    "out.quality": {Locale.EN: "Quality score", Locale.HI: "गुणवत्ता अंक", Locale.MR: "गुणवत्ता गुण"},
    "out.likely_range": {Locale.EN: "Likely range", Locale.HI: "संभावित दायरा",
                         Locale.MR: "संभाव्य श्रेणी"},
    "out.risk.low": {Locale.EN: "Low risk", Locale.HI: "कम खतरा", Locale.KN: "ಕಡಿಮೆ ಅಪಾಯ",
                     Locale.MR: "कमी धोका"},
    "out.risk.medium": {Locale.EN: "Medium risk", Locale.HI: "मध्यम खतरा",
                        Locale.KN: "ಮಧ್ಯಮ ಅಪಾಯ", Locale.MR: "मध्यम धोका"},
    "out.risk.high": {Locale.EN: "High risk", Locale.HI: "ज़्यादा खतरा",
                      Locale.KN: "ಹೆಚ್ಚಿನ ಅಪಾಯ", Locale.MR: "जास्त धोका"},
    "out.best_action": {Locale.EN: "Best thing to do", Locale.HI: "सबसे अच्छा उपाय",
                        Locale.MR: "सर्वोत्तम उपाय"},
    "out.drivers": {Locale.EN: "Main reasons", Locale.HI: "मुख्य कारण", Locale.MR: "मुख्य कारणे"},
    "out.saves": {Locale.EN: "saves", Locale.HI: "बचाएगा", Locale.MR: "वाचवेल"},
    "out.change_to": {Locale.EN: "change to", Locale.HI: "बदलकर करें", Locale.MR: "बदलून करा"},
    "out.biggest_unknown": {
        Locale.EN: "Pin this down to sharpen the estimate",
        Locale.HI: "यह पक्का कर लें तो अनुमान और सही होगा",
        Locale.MR: "हे निश्चित केल्यास अंदाज अधिक अचूक होईल",
    },
    # --- advisory sentence templates --------------------------------------
    # Placeholders are named so a translator can reorder them. Hindi is
    # subject-object-verb, so a positional template would force unnatural word
    # order in exactly the sentence that matters most.
    "msg.headline": {
        Locale.EN: "{qty} of {commodity}: about {loss} loss expected ({mass}).",
        Locale.HI: "{qty} {commodity} में करीब {loss} नुकसान का अनुमान है ({mass})।",
        Locale.MR: "{qty} {commodity} मध्ये सुमारे {loss} नुकसान अपेक्षित आहे ({mass}).",
    },
    "msg.rul": {
        Locale.EN: "It will sell fresh for about {hours} more.",
        Locale.HI: "यह करीब {hours} और ताज़ा बिकेगा।",
        Locale.MR: "हे सुमारे {hours} अधिक ताजे विकेल.",
    },
    "msg.action": {
        Locale.EN: "Best move: {label} — {change}. Saves about {mass}.",
        Locale.HI: "सबसे अच्छा उपाय: {label} — {change}। इससे करीब {mass} बचेगा।",
        Locale.MR: "सर्वोत्तम उपाय: {label} — {change}. यामुळे सुमारे {mass} वाचेल.",
    },
}


class MissingTranslation(KeyError):
    """Raised for an unknown key. A typo must fail loudly, not render blank."""


def t(key: str, locale: Locale = DEFAULT_LOCALE) -> str:
    """Look up `key`, walking the fallback chain.

    Returns the requested locale's string, else the first available fallback.
    An unknown *key* raises — that is a programming error and rendering an empty
    string in its place would hide it until a user saw the gap.
    """
    try:
        entry = STRINGS[key]
    except KeyError:
        raise MissingTranslation(
            f"no such string key: {key!r}. Add it to i18n.STRINGS."
        ) from None

    locale = Locale(locale)
    if locale in entry:
        return entry[locale]
    for candidate in FALLBACK_CHAIN.get(locale, (Locale.EN,)):
        if candidate in entry:
            return entry[candidate]
    return entry[Locale.EN]


def humanise(value: str) -> str:
    """`early_morning` -> `Early morning`. The last-resort readable form."""
    return str(value).replace("_", " ").strip().capitalize()


def option(value: str, locale: Locale = DEFAULT_LOCALE) -> str:
    """Localise a questionnaire answer, e.g. `open_truck` -> खुला ट्रक.

    **Never raises**, and that asymmetry against `t()` is deliberate.

    A missing *key* is a programming error, so `t()` raises and a typo fails
    loudly. A missing *option value* is something else entirely: option values
    arrive from the questionnaire content pack and from persisted user answers,
    neither of which this module owns. The questionnaire is already a superset of
    the engine's enums — it offers `post_harvest_shade: partial` and
    `harvest_window: early_morning` where the enums have `shade` and `morning`.

    Raising on those was a real bug with a nasty shape. Callers wrap the engine
    in a broad `except Exception` and degrade to a row with no interval but
    unchanged confidence, so an unknown answer surfaced as a confidently wrong
    number with no band rather than as an error anyone could see. Crashing on
    unexpected user data is how a loud failure becomes a silent one.

    So an unrecognised value degrades to a readable form of itself. Use
    `unknown_option_values()` to get the list worth translating properly.
    """
    key = f"opt.{value}"
    if key not in STRINGS:
        return humanise(value)
    return t(key, locale)


def unknown_option_values(values: object) -> list[str]:
    """Which of `values` have no translation — the worklist, not an error.

    Exists so the gap between the questionnaire's vocabulary and the engine's is
    reportable rather than something each caller rediscovers.
    """
    return sorted({str(v) for v in values if f"opt.{v}" not in STRINGS})


def field_label(name: str, locale: Locale = DEFAULT_LOCALE) -> str:
    return t(f"field.{name}", locale)


def commodity_name(key: str, locale: Locale = DEFAULT_LOCALE) -> str:
    return t(f"commodity.{key}", locale)


#: A locale must be at least this complete to be rendered at all.
#:
#: Per-key fallback is the obvious design and it is wrong across scripts. With
#: Kannada at 30% it produced sentences like "10,000 ಕೆ.ಜಿ. ಟೊಮ್ಯಾಟೊ में करीब
#: 72.5% नुकसान का अनुमान है" — Kannada nouns inside Hindi grammar, in two
#: scripts, which is harder to read than either language alone. A partly
#: translated locale is not a partly usable one.
#:
#: So below this threshold the *whole* render falls back to the next adequate
#: locale and the substitution is reported, letting the UI say "not yet
#: available in Kannada, showing Hindi" — which is a promise, where a
#: script-mixed sentence is just a bug the user has to decode.
MIN_USABLE_COVERAGE = 0.90


def resolve_locale(locale: Locale = DEFAULT_LOCALE) -> tuple[Locale, Locale | None]:
    """The locale that will actually render, and what was asked for instead.

    Returns `(effective, requested_but_unavailable)`. The second element is
    `None` when the request was honoured, so a caller can surface the
    substitution rather than silently swapping languages under the user.
    """
    locale = Locale(locale)
    if coverage(locale) >= MIN_USABLE_COVERAGE:
        return locale, None
    for candidate in FALLBACK_CHAIN.get(locale, (Locale.EN,)):
        if coverage(candidate) >= MIN_USABLE_COVERAGE:
            return candidate, locale
    return Locale.EN, locale


def coverage(locale: Locale) -> float:
    """Share of keys with a native string in this locale, before fallback.

    Reported rather than hidden: Kannada at partial coverage that degrades to
    Hindi is a known, stated gap. A number here is what lets D decide which
    locale needs a review pass before the demo.
    """
    locale = Locale(locale)
    present = sum(1 for entry in STRINGS.values() if locale in entry)
    return present / len(STRINGS)


def missing_keys(locale: Locale) -> list[str]:
    """Keys with no native string, in declaration order. The review worklist."""
    locale = Locale(locale)
    return [key for key, entry in STRINGS.items() if locale not in entry]
