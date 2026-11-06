"""Сборка всего пайплайна: понять → найти факт в базе → озвучить → проверить → записать.

assistant.reply() — единственная точка входа: CLI, веб-интерфейс и тесты идут через неё.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from .engine import decide
from .voice import speak

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "dialogs.jsonl"


def reply(question: str, log: bool = True) -> dict:
    started = time.perf_counter()
    decision = decide(question)
    voiced = speak(decision)

    result = {
        "question": question,
        "answer": voiced["text"],
        "decision": decision.decision,
        "rules": decision.rule_ids,
        "facts": decision.facts,
        "slots": decision.slots.as_dict(),
        "refused": decision.refused,
        "scope": decision.scope,
        "voice": voiced["source"],
        "guardrail": voiced["guardrail"],
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }

    if log:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now().isoformat(timespec="seconds"), **result}
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return result
