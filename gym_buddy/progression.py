from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any


_NUMBER_RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:[-–]\s*(\d+(?:\.\d+)?))?\s*$")


def target_amount_ceiling(value: Any) -> float | None:
    match = _NUMBER_RANGE.fullmatch(str(value))
    if not match:
        return None
    return float(match.group(2) or match.group(1))


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _session_succeeded(
    logs: list[Mapping[str, Any]], target_sets: int, target_amount: float
) -> tuple[bool, float | None]:
    planned_logs = [
        item
        for item in logs
        if 1 <= int(_number(item.get("set_number")) or 0) <= target_sets
    ]
    if len(planned_logs) != target_sets:
        return False, None
    set_numbers = {
        int(_number(item.get("set_number")) or 0) for item in planned_logs
    }
    if set_numbers != set(range(1, target_sets + 1)):
        return False, None

    amounts = [_number(item.get("actual_amount")) for item in planned_logs]
    weights = [_number(item.get("weight")) for item in planned_logs]
    if any(amount is None or amount < target_amount for amount in amounts):
        return False, None
    if any(weight is None or weight <= 0 for weight in weights):
        return False, None
    first_weight = weights[0]
    if any(not math.isclose(weight, first_weight, rel_tol=0.001) for weight in weights):
        return False, None
    return True, first_weight


def suggest_weight(
    logs: Iterable[Mapping[str, Any]],
    target_sets: int,
    target_amount: str,
    target_unit: str,
    weight_unit: str,
    increase_percent: float = 2.5,
) -> dict[str, Any]:
    target_ceiling = target_amount_ceiling(target_amount)
    if target_unit != "reps" or target_ceiling is None:
        return {
            "weight": None,
            "status": "No automatic weight suggestion for this target type.",
            "increased": False,
        }

    by_date: dict[date, list[Mapping[str, Any]]] = defaultdict(list)
    for log in logs:
        try:
            log_date = date.fromisoformat(str(log.get("date", ""))[:10])
        except ValueError:
            continue
        by_date[log_date].append(log)
    sessions = sorted(by_date.items(), key=lambda item: item[0])

    if not sessions:
        return {
            "weight": None,
            "status": "Log your working weight to start a history for this exercise.",
            "increased": False,
        }

    latest_logs = sessions[-1][1]
    latest_weights = [_number(item.get("weight")) for item in latest_logs]
    known_weights = [weight for weight in latest_weights if weight is not None]
    if not known_weights:
        return {
            "weight": None,
            "status": "No previous weight is recorded for this exercise.",
            "increased": False,
        }
    previous_weight = known_weights[-1]

    success_flags = [
        _session_succeeded(session_logs, target_sets, target_ceiling)
        for _, session_logs in sessions[-2:]
    ]
    if (
        len(success_flags) == 2
        and all(success for success, _ in success_flags)
        and math.isclose(
            success_flags[0][1] or 0,
            success_flags[1][1] or 0,
            rel_tol=0.001,
        )
    ):
        increment = 0.5 if weight_unit == "kg" else 2.5
        suggested = math.ceil(
            (previous_weight * (1 + increase_percent / 100) - 1e-9) / increment
        ) * increment
        suggested = round(max(suggested, previous_weight + increment), 2)
        return {
            "weight": suggested,
            "status": (
                "All target sets and reps were completed at the same weight "
                "in the last two sessions. Consider this small increase if it "
                "feels comfortable and your form stays controlled."
            ),
            "increased": True,
        }

    return {
        "weight": previous_weight,
        "status": "Use your most recently logged weight as a reference; keep building consistency.",
        "increased": False,
    }
