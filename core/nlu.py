"""Детерминированный слой понимания запроса: нормализация, слоты, интенты, инъекции.

Здесь нет нейросетей и не может быть «фантазии»: извлечение фактов из текста
выполняется правилами, которые можно прочитать и проверить.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

BASE_PATH = Path(__file__).with_name("regulations.json")


@dataclass
class Slots:
    """Факты, извлечённые из сообщения пользователя."""
    day_mentioned: int | None = None        # «на 16-й день», «через 5 дней»
    order_id: str | None = None             # «заказ 1842»
    discount_percent: int | None = None     # «скидку 20%»
    opened: bool = False                    # «вскрытые», «распечатан»
    defect: bool = False                    # «брак», «сломались»
    discount_request: bool = False          # «скидку», «промокод»
    asks_status: bool = False               # «где мой заказ», «статус»
    injection: bool = False                 # «забудь правила», «игнорируй инструкции»
    greeting: bool = False                  # «здравствуйте»
    thanks: bool = False                    # «спасибо»
    farewell: bool = False                  # «до свидания»
    exchange: bool = False                  # «обменять», «заменить»
    free_shipping: bool = False             # «бесплатная доставка»

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, False)}


# ─────────────────────────────── нормализация ───────────────────────────────
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("ё", "е").replace("Ё", "е")
    text = re.sub(r"[«»\"'`]", " ", text)
    text = re.sub(r"[^\w\s%₽\-\.:]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ────────────────────────────────── слоты ───────────────────────────────────
_DAYS_RE = re.compile(
    r"(?:на|через|спустя|по прошествии|в течение|в)\s*(\d{1,4})\s*"
    r"(?:-?\s*(?:й|ый|ой|ий|е|х|го|ому|ый))?\s*"
    r"(?:день|дня|дней|деньков|сутки|суток|дн)\b"
    r"|(\d{1,4})\s*[-–]?\s*(?:й|ый|ой|ий)\b"
    r"|(\d{1,4})\s*(?:день|дня|дней|суток|сутки)\b"
)
_PERCENT_RE = re.compile(r"(\d{1,3})\s*(?:%|процент\w*)")
_ORDER_RE = re.compile(r"(?:заказ\w*[^0-9]{0,12})?\b(\d{3,7})\b")
_OPENED_RE = re.compile(
    r"вскрыт\w*|распечатан\w*|открыт\w*|без\s+(?:коробк\w*|упаковк\w*|пленк\w*)"
    r"|был\w*\s+в\s+употреблен\w*|пользовал\w*|б\s*/\s*у|не\s+подош\w*|примерил\w*"
)
_DEFECT_RE = re.compile(
    r"брак\w*|дефект\w*|сломал\w*|сломан\w*|не\s+работа\w*|не\s+рабочи\w*|неисправн\w*"
    r"|шипит|хрипит|не\s+заряжа\w*|одна\s+сторон\w*|трещин\w*|биты\w*|погорел\w*"
)
_DISCOUNT_RE = re.compile(
    r"скидк\w*|промокод\w*|купон\w*|уступит\w*|дешевл\w*|торг\w*|поторгуем\w*"
    r"|бесплатн\w*|акци\w*|бонус\w*|в\s+подарок"
)
_STATUS_RE = re.compile(
    r"статус\w*|где\s+(?:мой\s+)?заказ|отследить|трек\w*|когда\s+(?:мой\s+)?заказ"
    r"|мой\s+заказ|посылк\w*|курьер\s+(?:уже|ещ[её])"
)
_GREETING_RE = re.compile(r"^\s*(?:здравствуй\w*|добр(?:ый|ое)\s+(?:день|вечер|утро)|привет\w*|хай|hello|добрый)\b")
_THANKS_RE = re.compile(r"^\s*(?:спасиб\w*|благодарю|thanks|thx)\b")
_FAREWELL_RE = re.compile(r"^\s*(?:пока|до\s+свидан\w*|всего\s+доброго|до\s+встречи)\b")
_EXCHANGE_RE = re.compile(r"обмен\w*|поменя\w*|замен\w*|другую\s+модель")
_FREE_SHIPPING_RE = re.compile(
    r"бесплатн\w*\s+(?:доставк\w*|отправк\w*|пересылк\w*)"
    r"|доставк\w*[^.]{0,25}бесплатн\w*"
    r"|доставк\w*[^.]{0,25}\b(?:сколько\s+стоит|платная)\b")
_INJECTION_RE = re.compile(
    r"забудь\s+(?:вс[её]|все\s+)?(?:правил\w*|инструкц\w*|прошл\w*|предыдущ\w*|ограничени\w*)"
    r"|забей\s+на\s+(?:правил\w*|инструкц\w*)"
    r"|игнорируй\s+(?:вс[её]|все\s+)?(?:правил\w*|инструкц\w*|предыдущ\w*|ограничени\w*)"
    r"|не\s+соблюдай\s+(?:правил\w*|инструкц\w*)"
    r"|отключи\s+(?:правил\w*|ограничени\w*|фильтр\w*|базу)"
    r"|отмени\s+(?:правил\w*|инструкц\w*)"
    r"|новы[ей]\s+(?:правил\w*|инструкц\w*| system)"
    r"|новая\s+инструкц\w*|новые\s+правила"
    r"|ты\s+теперь|представь\s+что\s+ты|притворись"
    r"|\bsystem\s*:|\bignore\s+(?:all|previous|the)\b|jailbreak|dan\s+mode"
    r"|(?:покажи|покажите|выведи|выдай|раскрой|скинь|отправь|озвучь)\s+"
    r"(?:сво[йю]\s+|твой\s+|текущ\w+\s+|системн\w+\s+|внутренн\w+\s+){0,3}"
    r"(?:промпт|system\s*prompt|инструкц\w*|правила)"
)


def extract_slots(raw_text: str) -> Slots:
    text = normalize(raw_text)
    slots = Slots()

    m = _PERCENT_RE.search(text)
    if m:
        slots.discount_percent = int(m.group(1))

    m = _DAYS_RE.search(text)
    if m:
        value = next((g for g in m.groups() if g), None)
        if value:
            slots.day_mentioned = int(value)

    if slots.discount_percent is None:  # 20% ≠ номер заказа
        m = _ORDER_RE.search(text)
        if m:
            slots.order_id = m.group(1)

    slots.opened = bool(_OPENED_RE.search(text))
    slots.defect = bool(_DEFECT_RE.search(text))
    slots.discount_request = bool(_DISCOUNT_RE.search(text))
    slots.asks_status = bool(_STATUS_RE.search(text))
    slots.injection = bool(_INJECTION_RE.search(text))
    slots.greeting = bool(_GREETING_RE.search(text))
    slots.thanks = bool(_THANKS_RE.search(text))
    slots.farewell = bool(_FAREWELL_RE.search(text))
    slots.exchange = bool(_EXCHANGE_RE.search(text))
    slots.free_shipping = bool(_FREE_SHIPPING_RE.search(text))
    return slots


# ───────────────────────────────── интенты ──────────────────────────────────
def load_base(path: Path = BASE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class Match:
    rule_id: str
    score: int
    hits: list[str] = field(default_factory=list)


def match_rules(base: dict, text_norm: str) -> list[Match]:
    """Взвешенное совпадение ключевых слов по каждому пункту регламента."""
    matches: list[Match] = []
    for rule in base["rules"]:
        score, hits = 0, []
        for word, weight in rule["keywords"].items():
            key = normalize(word)
            pattern = rf"(?<!\w){re.escape(key)}(?!\w)"
            if re.search(pattern, text_norm):
                score += weight
                hits.append(key)
        if score:
            matches.append(Match(rule["id"], score, hits))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def numbers_from(text: str) -> set[str]:
    """Числа из текста. Время «18:00» даёт только час (18), а не мусор вроде «00»."""
    out: set[str] = set()
    text = text or ""
    for m in re.finditer(r"\b(\d{1,2}):(\d{2})\b", text):
        out.add(m.group(1))
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", " ", text)
    for m in re.finditer(r"\d+(?:[\s ]\d{3})*", cleaned):
        out.add(m.group(0).replace(" ", "").replace("\u00a0", "").replace("\u202f", ""))
    return out
