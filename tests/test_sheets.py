from __future__ import annotations

from datetime import date
from typing import Any

import gspread
import pytest

from gym_buddy.plan import PLAN_COLUMNS
from gym_buddy.sheets import HEALTH_COLUMNS, WORKOUT_COLUMNS, SheetsStore


class FakeWorksheet:
    def __init__(self, title: str, rows: int = 100, cols: int = 20) -> None:
        self.title = title
        self.rows: list[list[str]] = []
        self.row_count = rows
        self.col_count = cols

    def get_all_values(self) -> list[list[str]]:
        return [row[:] for row in self.rows]

    def update(self, values: list[list[Any]], range_name: str) -> None:
        updated = [[str(cell) for cell in row] for row in values]
        if range_name == "A1" and self.rows:
            self.rows[0] = updated[0]
        else:
            self.rows = updated

    def clear(self) -> None:
        self.rows = []

    def append_rows(
        self, values: list[list[Any]], value_input_option: str = "RAW"
    ) -> None:
        self.rows.extend([[str(cell) for cell in row] for row in values])

    def append_row(
        self, values: list[Any], value_input_option: str = "RAW"
    ) -> None:
        self.rows.append([str(cell) for cell in values])

    def delete_rows(self, start: int, end: int | None = None) -> None:
        final = end or start
        del self.rows[start - 1 : final]


class FakeSpreadsheet:
    def __init__(self, worksheets: list[FakeWorksheet]) -> None:
        self._worksheets = {worksheet.title: worksheet for worksheet in worksheets}

    def worksheet(self, title: str) -> FakeWorksheet:
        try:
            return self._worksheets[title]
        except KeyError as exc:
            raise gspread.WorksheetNotFound(title) from exc

    def add_worksheet(
        self, title: str, rows: int, cols: int
    ) -> FakeWorksheet:
        worksheet = FakeWorksheet(title, rows, cols)
        self._worksheets[title] = worksheet
        return worksheet

    def worksheets(self) -> list[FakeWorksheet]:
        return list(self._worksheets.values())


def test_blank_workout_plan_tab_gets_headers_and_default_plan() -> None:
    blank_plan = FakeWorksheet("WorkoutPlan")
    blank_plan.rows = [["   "], [" "]]
    store = SheetsStore(FakeSpreadsheet([blank_plan]))

    assert tuple(blank_plan.get_all_values()[0]) == PLAN_COLUMNS
    assert len(store.get_plan()) > 0


def test_nonempty_plan_tab_with_wrong_headers_reports_clear_error() -> None:
    wrong_plan = FakeWorksheet("WorkoutPlan")
    wrong_plan.rows = [["not", "the", "expected", "headers"]]

    with pytest.raises(ValueError, match="unexpected columns"):
        SheetsStore(FakeSpreadsheet([wrong_plan]))


def test_activity_is_saved_to_year_tabs_and_previous_years_are_kept() -> None:
    store = SheetsStore(FakeSpreadsheet([]))
    exercise = {
        "id": "monday-bench-press",
        "exercise": "Bench Press",
    }

    for year, weight in ((2026, 50), (2027, 52)):
        log_date = date(year, 1, 5)
        store.save_exercise_sets(
            log_date,
            exercise,
            [
                {
                    "date": log_date.isoformat(),
                    "exercise_id": exercise["id"],
                    "exercise": exercise["exercise"],
                    "set_number": 1,
                    "target_amount": "5",
                    "actual_amount": 5,
                    "target_unit": "reps",
                    "weight": weight,
                    "weight_unit": "kg",
                    "logged_at": "",
                }
            ],
        )
        store.save_daily_health({"date": log_date.isoformat(), "steps": 1000})

    spreadsheet = store._spreadsheet
    assert spreadsheet.worksheet("WorkoutSets_2026").get_all_values()[0] == list(
        WORKOUT_COLUMNS
    )
    assert spreadsheet.worksheet("WorkoutSets_2027").get_all_values()[0] == list(
        WORKOUT_COLUMNS
    )
    assert spreadsheet.worksheet("DailyHealth_2026").get_all_values()[0] == list(
        HEALTH_COLUMNS
    )
    assert spreadsheet.worksheet("DailyHealth_2027").get_all_values()[0] == list(
        HEALTH_COLUMNS
    )
    assert [row["date"] for row in store.get_workout_logs()] == [
        "2026-01-05",
        "2027-01-05",
    ]
    assert [row["date"] for row in store.get_health_logs()] == [
        "2026-01-05",
        "2027-01-05",
    ]


def test_existing_health_tab_adds_attendance_header_without_losing_rows() -> None:
    old_columns = list(HEALTH_COLUMNS[:-1])
    old_health = FakeWorksheet("DailyHealth_2026")
    old_health.rows = [
        old_columns,
        ["2026-01-05", "30", "45", "6000", "1800", "2", "100", "68", "", "walk"],
    ]
    store = SheetsStore(FakeSpreadsheet([FakeWorksheet("WorkoutPlan"), old_health]))

    store.ensure_year(2026)
    records = store.get_health_logs()

    assert old_health.get_all_values()[0] == list(HEALTH_COLUMNS)
    assert records[0]["date"] == "2026-01-05"
    assert records[0]["gym_attended"] == ""
