"""Автотесты ассистента: 25 кейсов, включая три вопроса из ТЗ.

Запуск:  python tests/run_evals.py
Проверяет не только «что сказано», но и «чего сказано быть не может»
— именно это и есть защита от галлюцинаций.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.assistant import reply  # noqa: E402
from core.nlu import normalize, numbers_from  # noqa: E402
from core.voice import _asserts_allowance  # noqa: E402

CASES = json.loads((Path(__file__).with_name("cases.json")).read_text(encoding="utf-8"))
BASE_NUMBERS = {"2490", "14", "3", "18", "21", "1", "2"}  # 1, 2 — цифры в названиях моделей X1/X2


DELIVERY_ASSERTION_RE = re.compile(
    r"приедет|привезут|достав(?:ят|лен|ка будет)|в пути|передан\s+курьер|будет\s+доставлен")
NEGATION_RE = re.compile(r"\b(?:не|нет|значит\s+ли|не\s+знаю|не\s+могу|подтвердить\s+не\s+могу)\b")


def _asserts_delivery(text: str) -> bool:
    """Утверждает ли ответ дату/статус доставки?

    «Но значит ли это, что ваш заказ приедет завтра, я сказать не могу» — это
    не утверждение, а снятие догадки. Смотрим на контекст вокруг фразы.
    """
    for m in DELIVERY_ASSERTION_RE.finditer(text):
        context = text[max(0, m.start() - 70): m.end() + 90]
        if not NEGATION_RE.search(context):
            return True
    return False


def numbers_in(text: str) -> set[str]:
    return numbers_from(text)


def run() -> tuple[int, list[dict]]:
    passed, rows = 0, []
    for case in CASES:
        result = reply(case["question"], log=False)
        answer = result["answer"]
        errors = []

        if not result["decision"].startswith(case["expect_decision"]):
            errors.append(f"решение {result['decision']} ≠ {case['expect_decision']}")
        if result["refused"] != case["refused"]:
            errors.append(f"refused={result['refused']} (ожидалось {case['refused']})")
        for pattern in case.get("must_contain", []):
            if not re.search(pattern, answer, flags=re.IGNORECASE):
                errors.append(f"нет «{pattern}»")
        for pattern in case.get("must_not_contain", []):
            if re.search(pattern, answer, flags=re.IGNORECASE):
                errors.append(f"недопустимо «{pattern}»")

        if case.get("deny_delivery_assertion") and _asserts_delivery(normalize(answer)):
            errors.append("ответ утверждает дату или статус доставки")

        if case.get("deny_allowance") and _asserts_allowance(normalize(answer)):
            errors.append("ответ разрешает то, что регламент запрещает")

        # страховка: в ответе не должно быть чисел, которых нет ни в базе, ни в вопросе
        extra = numbers_in(answer) - BASE_NUMBERS - numbers_in(case["question"])
        if extra:
            errors.append(f"числа не из базы: {sorted(extra)}")

        ok = not errors
        passed += ok
        rows.append({"id": case["id"], "group": case["group"], "question": case["question"],
                     "decision": result["decision"], "answer": answer,
                     "ok": ok, "errors": errors})
    return passed, rows


def main() -> int:
    passed, rows = run()
    total = len(rows)
    lines = [f"Пройдено: {passed}/{total}", ""]
    for row in rows:
        mark = "✓" if row["ok"] else "✗"
        lines.append(f"{mark} [{row['id']}] {row['question']}")
        lines.append(f"    решение: {row['decision']}")
        lines.append(f"    ответ:   {row['answer']}")
        for err in row["errors"]:
            lines.append(f"    ОШИБКА:  {err}")
        lines.append("")

    report = "\n".join(lines)
    print(report)
    Path(__file__).with_name("REPORT.md").write_text(
        "# Отчёт автотестов\n\n```\n" + report + "```\n", encoding="utf-8")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
