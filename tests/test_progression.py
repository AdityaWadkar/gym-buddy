from datetime import date, timedelta

from gym_buddy.progression import suggest_weight, target_amount_ceiling


def _session(day: date, start_weight: float, count: int = 3) -> list[dict[str, object]]:
    return [
        {
            "date": day.isoformat(),
            "set_number": set_number,
            "actual_amount": 10,
            "weight": start_weight,
        }
        for set_number in range(1, count + 1)
    ]


def test_target_amount_ceiling_supports_fixed_and_range_targets() -> None:
    assert target_amount_ceiling("5") == 5
    assert target_amount_ceiling("8-10") == 10
    assert target_amount_ceiling("10–12") == 12
    assert target_amount_ceiling("Failure") is None


def test_suggests_increase_after_two_consistent_successes() -> None:
    today = date(2026, 11, 9)
    logs = _session(today - timedelta(days=7), 20) + _session(today, 20)

    result = suggest_weight(logs, 3, "8-10", "reps", "kg")

    assert result["weight"] == 20.5
    assert result["increased"] is True


def test_does_not_increase_after_incomplete_session() -> None:
    today = date(2026, 11, 9)
    logs = _session(today - timedelta(days=7), 20) + _session(today, 20, count=2)

    result = suggest_weight(logs, 3, "8-10", "reps", "kg")

    assert result["weight"] == 20
    assert result["increased"] is False


def test_does_not_increase_when_successful_sessions_used_different_weights() -> None:
    today = date(2026, 11, 9)
    logs = _session(today - timedelta(days=7), 20) + _session(today, 22)

    result = suggest_weight(logs, 3, "8-10", "reps", "kg")

    assert result["weight"] == 22
    assert result["increased"] is False


def test_extra_sets_do_not_block_progression_after_planned_sets_are_met() -> None:
    today = date(2026, 11, 9)
    first = _session(today - timedelta(days=7), 20)
    second = _session(today, 20) + [
        {
            "date": today.isoformat(),
            "set_number": 4,
            "actual_amount": 8,
            "weight": 20,
        }
    ]

    result = suggest_weight(first + second, 3, "8-10", "reps", "kg")

    assert result["weight"] == 20.5
    assert result["increased"] is True

