"""Голос ассистента: LLM переписывает ответ, guardrail проверяет, что она не соврала.

Правило простое: модель получает только факты, извлечённые из регламента, и не имеет
права выйти за них. Любое нарушение → ответ отбрасывается и берётся шаблон.
LLM здесь — не источник знаний, а только «редактор» уже найденной истины.
"""
from __future__ import annotations

import re

from . import llm
from .engine import Answer
from .nlu import normalize, numbers_from
from .prompt import REFUSAL_INSTRUCTION, SYSTEM_PROMPT

MAX_LEN = 700
SAFE_NUMBERS = {"1", "2"}  # цифры в названиях моделей: X1, X2


def _numbers_from(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"\d+(?:[\s ]\d{3})*", text or ""):
        out.add(m.group(0).replace(" ", "").replace(" ", ""))
    return out


def user_numbers(answer: Answer) -> set[str]:
    """Числа, сказанные самим клиентом: их повторять в ответе можно."""
    nums = numbers_from(answer.question)
    s = answer.slots
    for value in (s.day_mentioned, s.discount_percent, s.order_id):
        if value is not None:
            nums.add(str(value))
    return nums


def build_context(answer: Answer) -> str:
    facts = "\n".join(f"- {f}" for f in answer.facts) if answer.facts else "(пусто: подходящего пункта регламента нет)"
    parts = [
        f"ВОПРОС КЛИЕНТА: {answer.question}",
        f"РЕШЕНИЕ СЛОЯ ПРАВИЛ: {answer.decision}",
        f"FACTS:\n{facts}",
    ]
    if answer.refused and answer.scope == "out_of_base":
        parts.append(REFUSAL_INSTRUCTION)
    if answer.refused and answer.scope == "in_base":
        parts.append("Ответ — отказ. Коротко объясни причину, опираясь только на FACTS, и не предлагай того, чего в регламенте нет.")
    parts.append(f"ШАБЛОН ОТВЕТА (перепиши своими словами, смысл сохрани): {answer.text}")
    return "\n\n".join(parts)


ALLOWANCE_RE = re.compile(
    r"можно\s+вернуть|можете\s+вернуть|можно\s+оформить\s+возврат|возврат\s+возможен"
    r"|успеваете|успеете\s+вернуть|укладываетесь")
NEGATION_RE = re.compile(r"\b(?:не|нет|только|ист[её]к|истекл\w*|нельзя|уже\s+не)\b")


def _asserts_allowance(text: str) -> bool:
    """Разрешает ли ответ то, что регламент запрещает?

    Фраза «вскрытые наушники можно вернуть только в течение 14 дней, и срок истёк»
    — корректный отказ, хотя содержит «можно вернуть». Смотрим на контекст слева.
    """
    for m in ALLOWANCE_RE.finditer(text):
        # смотрим по обе стороны: «можно вернуть только в течение 14 дней, и срок истёк»
        # — это отказ, хотя слова «можно вернуть» в нём есть
        context = text[max(0, m.start() - 70): m.end() + 90]
        if not NEGATION_RE.search(context):
            return True
    return False


def verify(answer: Answer, candidate: str) -> tuple[bool, str]:
    """Проверка сгенерированного ответа. Возвращает (годится, причина)."""
    if not candidate or not candidate.strip():
        return False, "пустой ответ"
    if len(candidate) > MAX_LEN:
        return False, f"слишком длинно ({len(candidate)} символов)"

    text = normalize(candidate)

    for pattern in answer.banned:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return False, f"запрещённое утверждение: /{pattern}/"

    if answer.deny_allowance and _asserts_allowance(text):
        return False, "ответ разрешает то, что регламент запрещает"

    for pattern in answer.required:
        if not re.search(pattern, text, flags=re.IGNORECASE):
            return False, f"нет обязательного факта: /{pattern}/"

    allowed = set(answer.allowed_numbers) | user_numbers(answer) | SAFE_NUMBERS
    extra = numbers_from(candidate) - allowed
    if extra:
        return False, f"числа не из базы: {sorted(extra)}"

    if re.search(r"(?:facets|facts?\s*:|регламент(?:а|у|е)\s+пункт\s*\d|source:)", text):
        return False, "служебный текст в ответе"

    return True, "ok"


def speak(answer: Answer) -> dict:
    """Возвращает итоговый ответ + как он получен + результат проверки."""
    if llm.provider() is None:
        return {"text": answer.text, "source": "template", "guardrail": "не применялся (нет ключа LLM)"}

    try:
        raw = llm.complete(SYSTEM_PROMPT, build_context(answer))
    except Exception as exc:  # сеть, лимиты, битый ключ — не роняем бота
        return {"text": answer.text, "source": "template", "guardrail": f"сбой LLM: {exc}"}

    ok, reason = verify(answer, raw)
    if ok:
        return {"text": raw.strip(), "source": "llm", "guardrail": "проверка пройдена"}
    return {"text": answer.text, "source": "template", "guardrail": f"ответ модели отброшен: {reason}"}
