from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PLAN_COLUMNS = (
    "id",
    "day",
    "category",
    "exercise",
    "target_sets",
    "target_amount",
    "target_unit",
    "weighted",
    "is_core",
)


def _entry(
    day: str,
    category: str,
    name: str,
    sets: int,
    amount: str,
    unit: str,
    weighted: bool = False,
    core: bool = False,
) -> dict[str, Any]:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return {
        "id": f"{day.lower()}-{slug}",
        "day": day,
        "category": category,
        "exercise": name,
        "target_sets": sets,
        "target_amount": amount,
        "target_unit": unit,
        "weighted": weighted,
        "is_core": core,
    }


def default_plan() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def add(
        day: str,
        category: str,
        name: str,
        sets: int,
        amount: str,
        unit: str = "reps",
        weighted: bool = False,
        core: bool = False,
    ) -> None:
        entries.append(_entry(day, category, name, sets, amount, unit, weighted, core))

    add("Monday", "Strength", "Bench Press", 5, "5", weighted=True, core=True)
    add("Monday", "Strength", "Incline DB Press", 4, "8-10", weighted=True, core=True)
    add("Monday", "Strength", "Weighted Dips", 3, "10", weighted=True, core=True)
    add("Monday", "Strength", "Cable Fly", 3, "12", core=False)
    add("Monday", "Strength", "Pec Deck Drop Set", 2, "1", unit="sets")
    add("Monday", "Strength", "Skull Crushers", 4, "10", weighted=True)
    add("Monday", "Strength", "Rope Pushdown", 3, "12")
    add("Monday", "Strength", "Overhead Rope Extension", 3, "12")
    add(
        "Monday",
        "Cardio/Core",
        "Battle Rope HIIT (20s work / 40s rest)",
        10,
        "20",
        unit="seconds",
    )
    add("Monday", "Mobility", "Hanging", 3, "45", unit="seconds")
    add("Monday", "Mobility", "Cobra", 3, "30", unit="seconds")
    add("Monday", "Mobility", "Cat-Cow", 1, "10")

    add("Tuesday", "Strength", "Deadlift", 5, "5", weighted=True, core=True)
    add("Tuesday", "Strength", "Weighted Pull-ups", 4, "8", weighted=True, core=True)
    add("Tuesday", "Strength", "Barbell Row", 4, "8", weighted=True, core=True)
    add("Tuesday", "Strength", "Lat Pulldown", 3, "12", weighted=True)
    add("Tuesday", "Strength", "Seated Cable Row", 3, "12", weighted=True)
    add("Tuesday", "Strength", "Face Pull", 3, "15")
    add("Tuesday", "Strength", "EZ Bar Curl", 4, "10", weighted=True)
    add("Tuesday", "Strength", "Incline DB Curl", 3, "12", weighted=True)
    add("Tuesday", "Strength", "Hammer Curl", 3, "12", weighted=True)
    add("Tuesday", "Cardio/Core", "Hanging Leg Raises", 3, "15")
    add("Tuesday", "Cardio/Core", "Plank", 3, "60", unit="seconds")
    add("Tuesday", "Mobility", "Forward Bend", 3, "30", unit="seconds")
    add("Tuesday", "Mobility", "Pelvic Bridge", 3, "30", unit="seconds")
    add("Tuesday", "Mobility", "Hanging", 3, "45", unit="seconds")

    add("Friday", "Strength", "Back Squat", 5, "5", weighted=True, core=True)
    add("Friday", "Strength", "Romanian Deadlift", 4, "8", weighted=True, core=True)
    add("Friday", "Strength", "Bulgarian Split Squat", 3, "12", weighted=True, core=True)
    add("Friday", "Strength", "Leg Press", 4, "12", weighted=True)
    add("Friday", "Strength", "Leg Extension", 3, "15", weighted=True)
    add("Friday", "Strength", "Leg Curl", 3, "15", weighted=True)
    add("Friday", "Strength", "Standing Calf Raise", 5, "20", weighted=True)
    add("Friday", "Strength", "Seated Calf Raise", 4, "15", weighted=True)
    add("Friday", "Cardio/Core", "Stair Climber", 1, "10", unit="minutes")
    add("Friday", "Mobility", "Hip Flexor Stretch", 3, "30", unit="seconds")
    add("Friday", "Mobility", "Cobra", 3, "30", unit="seconds")
    add("Friday", "Mobility", "Hamstring Stretch", 3, "30", unit="seconds")

    add("Wednesday", "Strength", "Standing OHP", 5, "5", weighted=True, core=True)
    add("Wednesday", "Strength", "DB Shoulder Press", 4, "10", weighted=True, core=True)
    add("Wednesday", "Strength", "Lateral Raise", 5, "15", weighted=True, core=True)
    add("Wednesday", "Strength", "Rear Delt Fly", 4, "15", weighted=True)
    add("Wednesday", "Strength", "Upright Row", 3, "10", weighted=True)
    add("Wednesday", "Strength", "Shrugs", 4, "15", weighted=True)
    add("Wednesday", "Cardio/Core", "HIIT Bike", 1, "15", unit="minutes")
    add("Wednesday", "Cardio/Core", "Cable Crunch", 3, "15", weighted=True)
    add("Wednesday", "Cardio/Core", "Hanging Knee Raise", 3, "15")
    add("Wednesday", "Cardio/Core", "Russian Twist", 3, "20")
    add("Wednesday", "Mobility", "Hanging", 3, "45", unit="seconds")
    add("Wednesday", "Mobility", "Side Stretch", 3, "30", unit="seconds")
    add("Wednesday", "Mobility", "Cat-Cow", 1, "10")

    add("Thursday", "Strength", "Barbell Curl", 4, "8", weighted=True, core=True)
    add("Thursday", "Strength", "Preacher Curl", 3, "12", weighted=True, core=True)
    add("Thursday", "Strength", "Bayesian Cable Curl", 3, "15", weighted=True, core=True)
    add("Thursday", "Strength", "Close-Grip Bench Press", 4, "8", weighted=True)
    add("Thursday", "Strength", "Rope Pushdown", 3, "12")
    add("Thursday", "Strength", "Overhead Extension", 3, "12")
    add("Thursday", "Strength", "Bench Dips", 3, "Failure")
    add("Thursday", "Strength", "Wrist Curl", 3, "20", weighted=True)
    add("Thursday", "Strength", "Reverse Wrist Curl", 3, "20", weighted=True)
    add("Thursday", "Strength", "Farmer's Walk", 3, "1", unit="rounds", weighted=True)
    add("Thursday", "Cardio/Core", "Incline Treadmill Walk", 1, "10-15", unit="minutes")
    add("Thursday", "Mobility", "Pelvic Bridge", 3, "30", unit="seconds")
    add("Thursday", "Mobility", "Forward Bend", 3, "30", unit="seconds")
    add("Thursday", "Mobility", "Hanging", 3, "45", unit="seconds")

    for index, (name, amount, unit) in enumerate(
        (
            ("Burpees", "10", "reps"),
            ("Kettlebell Swings", "15", "reps"),
            ("Push-ups", "20", "reps"),
            ("Walking Lunges", "20", "reps"),
            ("Box Jumps", "15", "reps"),
            ("Row", "250", "meters"),
            ("Battle Rope", "30", "seconds"),
        )
    ):
        add("Saturday", "Conditioning", name, 5, amount, unit, core=index < 3)
    add("Saturday", "Mobility", "Jump Rope", 3, "60", unit="seconds")
    add("Saturday", "Mobility", "Full Body Mobility", 1, "1", unit="session")
    add("Saturday", "Mobility", "Cobra", 3, "30", unit="seconds")
    add("Saturday", "Mobility", "Hip Mobility", 1, "1", unit="session")

    add("Sunday", "Active Recovery", "Light Mobility Workout", 1, "1", unit="session", core=True)
    add("Sunday", "Active Recovery", "Resistance Bands", 1, "1", unit="session")
    add("Sunday", "Active Recovery", "Walk", 1, "30-45", unit="minutes", core=True)
    add("Sunday", "Cardio/Core", "Plank", 2, "45", unit="seconds")
    add("Sunday", "Mobility", "Full Body Stretch", 1, "1", unit="session")
    add("Sunday", "Mobility", "Foam Rolling", 1, "1", unit="session")
    add("Sunday", "Mobility", "Hanging", 3, "45", unit="seconds")
    add("Sunday", "Mobility", "Hip & Shoulder Mobility", 1, "1", unit="session")

    return entries


def row_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["target_sets"] = int(result["target_sets"])
    result["weighted"] = _as_bool(result.get("weighted", False))
    result["is_core"] = _as_bool(result.get("is_core", False))
    return result


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def normalize_plan(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        day = str(row.get("day", "")).strip()
        category = str(row.get("category", "")).strip()
        exercise = str(row.get("exercise", "")).strip()
        amount = str(row.get("target_amount", "")).strip()
        unit = str(row.get("target_unit", "")).strip()
        try:
            target_sets = int(row.get("target_sets", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Row {index}: target sets must be a whole number.") from exc
        if day not in DAYS:
            raise ValueError(f"Row {index}: choose a valid day of the week.")
        if not category or not exercise or not amount or not unit:
            raise ValueError(f"Row {index}: category, exercise, target, and unit are required.")
        if target_sets < 1:
            raise ValueError(f"Row {index}: target sets must be at least 1.")

        slug = re.sub(r"[^a-z0-9]+", "-", exercise.lower()).strip("-")
        row_id = str(row.get("id", "")).strip() or f"{day.lower()}-{slug}"
        if row_id in seen_ids:
            row_id = f"{row_id}-{index}"
        seen_ids.add(row_id)
        normalized.append(
            {
                "id": row_id,
                "day": day,
                "category": category,
                "exercise": exercise,
                "target_sets": target_sets,
                "target_amount": amount,
                "target_unit": unit,
                "weighted": _as_bool(row.get("weighted", False)),
                "is_core": _as_bool(row.get("is_core", False)),
            }
        )
    return normalized
