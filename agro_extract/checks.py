"""Deterministic checks of an extracted record against its source text.

Two kinds of checks, with different reactions:

* Numbers (strict): every value must be written in the text in the right context.
  - min_mm / max_mm: the number is followed by "мм" / "mm" within a short window
    ("11-20 мм", "від 173 до 282 мм"), not just any number anywhere in the text (a date, a %);
  - production_mt: the number is followed by "Mt" / "млн т";
  - mm values always need a soil layer.
  A violation makes the answer invalid: one correction attempt, then status "failed".

* Everything else (soft): unsupported values are removed or reset and logged in "removed"; the
  answer stays valid, so one wrong detail does not throw away the correct fields:
  - year / month / decade must be written in the text (month name, "першу / другу / третю
    декаду") -> else null;
  - soil layer: "0-20cm" needs "орний шар / 0-20 см / arable", "0-100cm" needs "метровий шар /
    0-100 см / metre", "both" needs both -> else the layer the text does mention, or "not_stated";
  - moisture status: "deficit" / "adequate" / "excess" need words of that class, "mixed" needs
    words of two classes -> else "not_stated";
  - every oblast in deficit_oblasts, every crop in crops / yield_outlook and every hazard must be
    supported by a keyword in the text (unsupported items are removed, duplicates too);
  - a crop condition (good / satisfactory / poor) needs a condition word, and a BBCH stage a word
    of that growth phase, within NEAR_WINDOW (250) characters of the crop name -> else
    "not_stated" / null (a condition taken from a general phrase or another crop is reset);
  - a crop with neither a stage nor a condition, and a yield entry with neither a comparison nor a
    production figure, carry no information and are removed;
  - above / near / below the average needs "5-year / average / середн" -> else "not_stated".

Keyword checks catch invented values, but not a word that is present and refers to something
else (e.g. "задовільне" about moisture, not crops). The 250-character window was chosen on the
golden set: the smallest window that keeps every golden value (100-150 would reset 2 of them).

Texts come from PDF extraction, so names may be split by spaces ("Кіровогр адської"); the
keyword search also runs on the text with all whitespace removed.
"""

import re

# ---------- text helpers ----------

def _join_digits(text: str) -> str:
    """PDF extraction breaks numbers: "2 2 мм" -> "22 мм"."""
    return re.sub(r"(?<=\d) (?=\d)", "", text)


def _squash(text: str) -> str:
    """Lowercase text without whitespace: catches words split by PDF extraction."""
    return re.sub(r"\s+", "", text.lower())


def _number_pattern(value: float) -> str:
    if float(value).is_integer():
        n = str(int(value))
        return rf"(?<![\d.,]){n}(?:[.,]0+)?(?![\d])"
    s = f"{value:g}"
    return rf"(?<![\d.,]){re.escape(s).replace(r'\.', '[.,]')}\d*(?![\d])"


def number_with_unit(text: str, value: float, unit: str, window: int) -> bool:
    """True if `value` is written in the text and followed by `unit` within `window` characters."""
    t = _join_digits(text)
    for m in re.finditer(_number_pattern(value), t):
        if re.search(unit, t[m.end(): m.end() + window], re.I):
            return True
    return False


MM_UNIT = r"мм|mm|мл"            # "мл" is a typo for мм in one bulletin ("більше 200 мл")
MT_UNIT = r"^\s*(?:mt\b|млн\.?\s*т|million\s+t)"
MM_WINDOW, MT_WINDOW = 30, 12

MONTHS = {
    1: r"січн|січен|january", 2: r"лютого|лютий|february", 3: r"березн|березен|march",
    4: r"квітн|квітен|april", 5: r"травн|травен|\bmay\s+20\d\d|\bin\s+may\b|\b(?:mid|early|late)-?\s?may\b",
    6: r"червн|червен|june", 7: r"липн|липен|july", 8: r"серпн|серпен|august",
    9: r"вересн|вересен|september", 10: r"жовтн|жовтен|october", 11: r"листопад|november",
    12: r"грудн|груден|december",
}
DECADES = {1: r"перш\w*\s+декад|first\s+dekad", 2: r"друг\w*\s+декад|second\s+dekad",
           3: r"трет\w*\s+декад|third\s+dekad"}


def fact_problems(rec, text: str) -> list[str]:
    """Strict checks of numbers and dates. Returns a list of problems (empty if all is fine)."""
    problems = []
    low = text.lower()
    sm = rec.soil_moisture
    for name in ("min_mm", "max_mm"):
        v = getattr(sm, name)
        if v is not None and not number_with_unit(text, v, MM_UNIT, MM_WINDOW):
            problems.append(f"soil_moisture.{name}={v} is not written in the text as a value in mm")
    for y in rec.yield_outlook:
        if y.production_mt is not None and not number_with_unit(text, y.production_mt, MT_UNIT, MT_WINDOW):
            problems.append(f"yield_outlook[{y.crop}].production_mt={y.production_mt} "
                            "is not written in the text as a value in Mt / млн т")
    # mm values always belong to a soil layer
    if (sm.min_mm is not None or sm.max_mm is not None) and sm.layer == "not_stated":
        problems.append("soil_moisture: mm values are given, so layer cannot be not_stated")
    return problems


# ---------- keyword support for values ----------

OBLAST_KEYS = {
    "vinnytsia": [r"вінниц", r"vinnyts"],
    "volyn": [r"волин", r"volyn"],
    "dnipropetrovsk": [r"дніпропетров", r"dnipropetrovs", r"dnipro"],
    "donetsk": [r"донецьк", r"donets"],
    "zhytomyr": [r"житомир", r"zhytomyr"],
    "zakarpattia": [r"закарпат", r"zakarpat", r"transcarpat"],
    "zaporizhzhia": [r"запоріз", r"zaporiz"],
    "ivano_frankivsk": [r"івано-франків", r"ivano-frankivs", r"ivano"],
    "kyiv": [r"київськ", r"київщин", r"kyivs", r"kyiv\s+oblast"],
    "kirovohrad": [r"кіровоград", r"kirovohrad", r"kropyvnyts"],
    "luhansk": [r"луганськ", r"luhans"],
    "lviv": [r"львів", r"lviv"],
    "mykolaiv": [r"миколаїв", r"mykolai"],
    "odesa": [r"одес", r"одещин", r"odesa", r"odes'?ka", r"odessa"],
    "poltava": [r"полтав", r"poltav"],
    "rivne": [r"рівненськ", r"rivne", r"rivnens"],
    "sumy": [r"сумськ", r"сумщин", r"sumy", r"sums'k"],
    "ternopil": [r"тернопіл", r"ternopil"],
    "kharkiv": [r"харків", r"kharkiv"],
    "kherson": [r"херсон", r"kherson"],
    "khmelnytskyi": [r"хмельниц", r"khmelnyts"],
    "cherkasy": [r"черкас", r"cherkas"],
    "chernivtsi": [r"чернівец", r"chernivts"],
    "chernihiv": [r"чернігів", r"chernihiv"],
    "crimea": [r"крим", r"crimea"],
}

CROP_KEYS = {
    "winter_wheat": [r"пшениц", r"wheat"],
    "winter_barley": [r"ячмін", r"ячмен", r"barley"],
    "spring_barley": [r"ячмін", r"ячмен", r"barley"],
    "winter_rapeseed": [r"ріпак", r"rapeseed", r"\brape\b"],
    "maize": [r"кукурудз", r"maize", r"\bcorn\b"],
    "sunflower": [r"соняшник", r"sunflower"],
    "soybean": [r"\bсо[яїюєя]\b", r"\bсої\b", r"soy"],
    "sugar_beet": [r"буряк", r"beet"],
}

HAZARD_KEYS = {
    "drought": [r"посух", r"засух", r"сухові", r"\bсух\w*", r"drought", r"\bdry", r"\bdrier",
                r"rain\w*\s+deficit", r"deficit\s+of\s+rain", r"дефіцит\w*\s+опад"],
    "frost": [r"заморозк", r"мороз", r"вимерз", r"frost", r"cold\s+snap"],
    "heat": [r"спек", r"\bжар", r"\bheat", r"high\s+temperatur", r"високі?\w*\s+температур"],
    "heavy_rain": [r"злив", r"сильн\w*\s+дощ", r"рясн\w*\s+дощ", r"надмірн\w*\s+кількіст\w*\s+опад",
                   r"heavy\s+rain", r"excess\w*\s+(?:\w+\s+)?rain", r"rainfall\s+excess", r"wetter"],
    "waterlogging": [r"перезволож", r"надмірн\w*\s+зволож", r"надмірн\w*\s+волог", r"waterlog",
                     r"excess\w*\s+(?:soil\s+)?moisture", r"wet\s+conditions"],
    "hail": [r"\bград\b", r"\bградом\b", r"\bhail"],
    "hostilities": [r"війн", r"бойов", r"окупов", r"\bwar\b", r"hostilit", r"occupi", r"occupation",
                    r"front\s*line", r"military", r"abandon"],
}


LAYER_KEYS = {
    "0-20cm": [r"орн", r"0\s*-\s*20\s*см", r"arable", r"topsoil", r"upper\s+(?:soil\s+)?layer"],
    "0-100cm": [r"метров", r"метров\w*\s+шар", r"0\s*-\s*100\s*см", r"\bmetre", r"\bmeter", r"one-metre"],
}

STATUS_KEYS = {
    "deficit": [r"(?<!не)недостатн", r"незадовільн", r"посух", r"засух", r"\bсух", r"понижен", r"дефіцит",
                r"deficit", r"\bdry", r"\bdrier", r"drought", r"insufficient"],
    "adequate": [r"(?<!не)достатн", r"оптимальн", r"(?<!не)задовільн", r"adequate", r"sufficient",
                 r"favourab", r"favorab", r"\bgood\s+water", r"near-normal|normal\s+soil"],
    "excess": [r"перезволож", r"надмірн", r"excess", r"waterlog", r"wetter", r"too\s+wet"],
}

CONDITION_KEYS = {
    "good": [r"добр", r"\bgood", r"favourab", r"favorab", r"excellent"],
    "satisfactory": [r"(?<!не)задовільн", r"\bfair", r"average", r"satisfactor", r"mediocre"],
    "poor": [r"поган", r"слабк", r"незадовільн", r"\bpoor", r"\bbad\b", r"weak"],
}

BBCH_KEYS = {
    0: [r"сход", r"пророст", r"germinat", r"emergen"],
    1: [r"лист", r"розетк", r"\bleaf", r"\bleaves"],
    2: [r"кущ", r"бокових\s+пагон", r"tiller", r"side\s+shoot"],
    3: [r"трубк", r"стебл", r"соломин", r"stem\s+elong", r"jointing", r"вузл"],
    4: [r"прапорцев", r"booting", r"корен", r"\broot", r"бульб"],
    5: [r"колос", r"суцвіт", r"бутон", r"кошик", r"волот", r"heading", r"inflorescence", r"\bear\s+emerg", r"\bbud"],
    6: [r"цвіт", r"flower", r"anthes"],
    7: [r"молочн", r"налив", r"формуван\w*\s+(?:зерн|бобів|насін)", r"grain\s+fill", r"\bmilk", r"\bpods?\b"],
    8: [r"воскова", r"воскової", r"стиглост", r"достиг", r"ripen", r"\bwax"],
    9: [r"повн\w*\s+стиглост", r"збиральн", r"harvest", r"збиранн", r"збір\s+урож"],
}

AVERAGE_KEYS = [r"5\s*-?\s*year", r"five-year", r"average", r"середн", r"п'ятирічн", r"багаторічн"]


def supported(text: str, patterns: list[str]) -> bool:
    low = text.lower()
    squashed = _squash(text)
    for p in patterns:
        if re.search(p, low):
            return True
        if "\\b" not in p and " " not in p and "\\s" not in p and re.search(p, squashed):
            return True   # word split by PDF extraction ("кіровогр адської")
    return False


NEAR_WINDOW = 250   # characters between a crop name and its condition / stage word


def _positions(text: str, patterns: list[str]) -> list[int]:
    low = _join_digits(text).lower()
    return [m.start() for p in patterns for m in re.finditer(p, low)]


def near(text: str, crop_patterns: list[str], word_patterns: list[str], window: int = NEAR_WINDOW) -> bool:
    """True if a crop name and a condition / stage word stand within `window` characters.
    Words split by PDF extraction are looked up in the text without spaces."""
    a, b = _positions(text, crop_patterns), _positions(text, word_patterns)
    if not a or not b:
        sq = _squash(text)
        plain = lambda ps: [p for p in ps if "\\b" not in p and "\\s" not in p and " " not in p]
        a = a or [m.start() for p in plain(crop_patterns) for m in re.finditer(p, sq)]
        b = b or [m.start() for p in plain(word_patterns) for m in re.finditer(p, sq)]
    return any(abs(i - j) <= window for i in a for j in b)


def clean_lists(rec: dict, text: str) -> tuple[dict, list[str]]:
    """Remove or reset values the text does not support. Returns (clean record, removed items)."""
    rec = {**rec, "soil_moisture": {**rec["soil_moisture"]}}
    removed = []
    _reset_facts(rec, text, removed)
    oblasts = []
    for o in rec["soil_moisture"]["deficit_oblasts"]:
        if supported(text, OBLAST_KEYS.get(o, [o])):
            oblasts.append(o)
        else:
            removed.append(f"deficit_oblasts:{o}")
    rec["soil_moisture"]["deficit_oblasts"] = _dedupe(oblasts, "deficit_oblasts", removed)
    crops = []
    for c in rec["crops"]:
        if not supported(text, CROP_KEYS.get(c["crop"], [c["crop"]])):
            removed.append(f"crops:{c['crop']}")
            continue
        c = dict(c)
        crop_keys = CROP_KEYS.get(c["crop"], [c["crop"]])
        if c["condition"] != "not_stated" and not near(text, crop_keys, CONDITION_KEYS[c["condition"]]):
            removed.append(f"crops[{c['crop']}].condition:{c['condition']}")
            c["condition"] = "not_stated"
        stage = c.get("bbch_stage")
        if stage is not None and not near(text, crop_keys, BBCH_KEYS.get(stage, [])):
            removed.append(f"crops[{c['crop']}].bbch_stage:{stage}")
            c["bbch_stage"] = None
        if c.get("bbch_stage") is None and c["condition"] == "not_stated":
            removed.append(f"crops:{c['crop']} (no stage, no condition)")
            continue
        crops.append(c)
    rec["crops"] = crops
    yields = []
    for y in rec["yield_outlook"]:
        if not supported(text, CROP_KEYS.get(y["crop"], [y["crop"]])):
            removed.append(f"yield_outlook:{y['crop']}")
            continue
        y = dict(y)
        if y["vs_5yr_average"] != "not_stated" and not supported(text, AVERAGE_KEYS):
            removed.append(f"yield_outlook[{y['crop']}].vs_5yr_average:{y['vs_5yr_average']}")
            y["vs_5yr_average"] = "not_stated"
        if y["vs_5yr_average"] == "not_stated" and y.get("production_mt") is None:
            removed.append(f"yield_outlook:{y['crop']} (no comparison, no production)")
            continue
        yields.append(y)
    rec["yield_outlook"] = yields
    hazards = []
    for h in rec["hazards"]:
        if supported(text, HAZARD_KEYS.get(h, [h])):
            hazards.append(h)
        else:
            removed.append(f"hazards:{h}")
    rec["hazards"] = _dedupe(hazards, "hazards", removed)
    return rec, removed


def _reset_facts(rec: dict, text: str, removed: list) -> None:
    """Single values the text does not support are reset to null / "not_stated"."""
    low = text.lower()
    if "year" in rec and rec["year"] is not None and not re.search(rf"(?<!\d){rec['year']}(?!\d)", _join_digits(text)):
        removed.append(f"year:{rec['year']}")
        rec["year"] = None
    if "month" in rec and rec["month"] is not None and rec["month"] in MONTHS and not re.search(MONTHS[rec["month"]], low):
        removed.append(f"month:{rec['month']}")
        rec["month"] = None
    if "decade" in rec and rec["decade"] is not None and rec["decade"] in DECADES and not re.search(DECADES[rec["decade"]], low):
        removed.append(f"decade:{rec['decade']}")
        rec["decade"] = None
    sm = rec["soil_moisture"]
    layer = sm.get("layer")
    need = {"0-20cm": ["0-20cm"], "0-100cm": ["0-100cm"], "both": ["0-20cm", "0-100cm"]}.get(layer, [])
    if need and not all(supported(text, LAYER_KEYS[l]) for l in need):
        present = [l for l in ("0-20cm", "0-100cm") if supported(text, LAYER_KEYS[l])]
        new_layer = present[0] if len(present) == 1 else ("both" if len(present) == 2 else "not_stated")
        if not (new_layer == "not_stated" and (sm.get("min_mm") is not None or sm.get("max_mm") is not None)):
            removed.append(f"soil_moisture.layer:{layer}->{new_layer}")
            sm["layer"] = new_layer
    status = sm.get("status")
    if status in ("deficit", "adequate", "excess") and not supported(text, STATUS_KEYS[status]):
        removed.append(f"soil_moisture.status:{status}")
        sm["status"] = "not_stated"
    elif status == "mixed" and sum(supported(text, STATUS_KEYS[c]) for c in ("deficit", "adequate", "excess")) < 2:
        removed.append("soil_moisture.status:mixed")
        sm["status"] = "not_stated"


def _dedupe(items: list, field: str, removed: list) -> list:
    out = []
    for i in items:
        if i in out:
            removed.append(f"{field}:{i} (duplicate)")
        else:
            out.append(i)
    return out
