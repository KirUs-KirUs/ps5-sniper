"""Определение: продаётся ли физическая PS5, какая модель и есть ли дисковод."""
import re

# Все варианты написания PS5: ps5, ps 5, ps-5, пс5, playstation 5, плейстейшн 5, sony play station 5 ...
PS5 = re.compile(
    r"(?<![a-zа-я0-9])(?:ps|пс|play\s?station|плей\s?стейшн|плейстейшен|плэйстейшн|плейстэйшн)"
    r"\s*-?\s*5(?![0-9])"
)

# Всегда исключаем, если встречается в заголовке
HARD_EXCLUDE = re.compile(
    r"аренд|прокат|посуточн|куплю|скупа|скупк|купим|выкуп|обмен\w*\s+.{0,40}\bна\s+(?:ps|пс|play)"
    r"|ремонт|^s*прошивк|услуг|подписк|ps\s?plus|ps\s?store|аккаунт|акаунт|запчаст|portal|портал|донат|пополнен|\bvr\s?2?\b|виртуальн|шлем|очки"
    r"|^\s*(?:игр[аыу]|диск[иа]?|геймпад|gamepad|джойстик|dualsense|контроллер)\b"
)

# Товар «для/на/под PS5» — игра или аксессуар
FOR_PS5 = re.compile(r"\b(?:для|на|под)\s+(?:sony\s+)?(?:ps|пс|play\s?station|плей)")

# Аксессуары/игры, стоящие в заголовке ДО упоминания PS5 («Геймпад DualSense PS5»)
ACCESSORY = re.compile(
    r"геймпад|gamepad|джойстик|dualsense|контроллер|controller|диск[иа]?\b|игр[аыу]\b|games?\b"
    r"|подставк|стойк|наушник|гарнитур|зарядн|кабел|чехол|наклейк|кулер|ssd|дисковод|привод"
)

OTHER_CONSOLE = re.compile(r"xbox|иксбокс|nintendo|switch|ps\s?[1-4]\b|пс\s?[1-4]\b|playstation\s?[1-4]\b|psp|ps\s?vita")

GENERIC_TITLE = re.compile(r"приставк|консол|console|playstation|плейстейшн|sony|сони")

DISC_NO = re.compile(r"без\s+(?:дисковод|привод)|no\s+disc|discless")
DISC_YES = re.compile(r"дисковод|привод(?:ом|а)?\b|\bdisc\b|blu-?\s?ray|дисковая|с\s+диском|standard\s+edition")
DIGITAL = re.compile(r"digital|диджитал|дижитал|цифров")


def _norm(s: str) -> str:
    return (s or "").lower().replace("ё", "е")


def _model(s: str) -> str | None:
    if re.search(r"\bpro\b|(?<![а-я])про(?![а-я])", s):
        return "Pro"
    if re.search(r"slim|слим", s):
        return "Slim"
    if re.search(r"\bfat\b|фат|толст|cfi-?10", s):
        return "Fat"
    return None


def _disc(s: str) -> str:
    if DISC_NO.search(s):
        return "no"
    if DISC_YES.search(s):
        return "yes"
    if DIGITAL.search(s):
        return "no"
    return "unknown"


def classify(title: str, text: str = "") -> dict:
    t, x = _norm(title), _norm(text)
    res = {"is_ps5": False, "model": None, "disc": None, "reason": "", "mixed": bool(OTHER_CONSOLE.search(t))}

    m = PS5.search(t)
    source = t
    if not m:
        # заголовок общий («Продам приставку») — смотрим текст
        if GENERIC_TITLE.search(t) and not OTHER_CONSOLE.search(t) and PS5.search(x):
            source = x
            m = PS5.search(x)
        else:
            res["reason"] = "нет PS5 в заголовке"
            return res

    if HARD_EXCLUDE.search(t):
        res["reason"] = "исключено: " + HARD_EXCLUDE.search(t).group()
        return res
    before = t[: m.start()] if source is t else ""
    if FOR_PS5.search(t) or ACCESSORY.search(before):
        res["reason"] = "аксессуар/игра для PS5"
        return res
    if OTHER_CONSOLE.search(before):
        res["reason"] = "другая консоль"
        return res

    title_disc = _disc(t)
    disc = title_disc if title_disc != "unknown" else _disc(x)
    res["disc"] = disc
    if disc == "no":
        res["reason"] = "без дисковода (Digital)"
        return res

    res.update(is_ps5=True, model=_model(t) or _model(x) or "PS5", reason="ok")
    return res
