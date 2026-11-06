"""Терминальный чат с ассистентом — удобно для записи видео-демо.

Запуск:  python chat.py
Команды: /why — показать решение, факты и проверку; /q — выйти.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import llm  # noqa: E402
from core.assistant import reply  # noqa: E402

BANNER = """Ассистент поддержки интернет-магазина
Режим озвучки: {voice}
Команды: /why — разбор последнего ответа, /q — выход
"""


def main() -> None:
    provider = llm.provider()
    print(BANNER.format(voice=f"{provider} ({llm.model_name()})" if provider else "шаблоны, ключ LLM не задан"))
    last: dict | None = None
    while True:
        try:
            question = input("\nКлиент: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in {"/q", "quit", "exit"}:
            break
        if question.lower() == "/why":
            if not last:
                print("  (ещё не было ответа)")
                continue
            print(f"  решение:   {last['decision']}")
            print(f"  правила:   {', '.join(last['rules'])}")
            print(f"  слоты:     {last['slots']}")
            print(f"  факты:     {last['facts'] or '— подходящего пункта в базе нет —'}")
            print(f"  источник:  {last['voice']}")
            print(f"  проверка:  {last['guardrail']}")
            continue

        last = reply(question)
        print(f"Бот: {last['answer']}")


if __name__ == "__main__":
    main()
