from gym_buddy.plan import DAYS, default_plan, normalize_plan


def test_default_plan_covers_all_days_and_keeps_short_sessions_compact() -> None:
    plan = default_plan()

    assert {row["day"] for row in plan} == set(DAYS)
    assert all(1 <= len([row for row in plan if row["day"] == day and row["is_core"]]) <= 4 for day in DAYS)


def test_default_plan_shifts_wednesday_thursday_and_friday_workouts() -> None:
    plan = default_plan()
    exercises_by_day = {
        day: {row["exercise"] for row in plan if row["day"] == day}
        for day in ("Wednesday", "Thursday", "Friday")
    }

    assert "Standing OHP" in exercises_by_day["Wednesday"]
    assert "Barbell Curl" in exercises_by_day["Thursday"]
    assert "Back Squat" in exercises_by_day["Friday"]
    assert len(exercises_by_day["Wednesday"]) == 13
    assert len(exercises_by_day["Thursday"]) == 14
    assert len(exercises_by_day["Friday"]) == 12


def test_default_plan_includes_exercise_targets_without_assuming_weights() -> None:
    plan = default_plan()
    bench_press = next(row for row in plan if row["exercise"] == "Bench Press")

    assert bench_press["target_sets"] == 5
    assert bench_press["target_amount"] == "5"
    assert bench_press["weighted"] is True
    assert "weight" not in bench_press


def test_normalize_plan_generates_ids_for_new_rows() -> None:
    plan = normalize_plan(
        [
            {
                "day": "Monday",
                "category": "Strength",
                "exercise": "New Exercise",
                "target_sets": 3,
                "target_amount": "8-10",
                "target_unit": "reps",
                "weighted": True,
                "is_core": False,
            }
        ]
    )

    assert plan[0]["id"] == "monday-new-exercise"
