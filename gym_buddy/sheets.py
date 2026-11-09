from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
import re
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from gym_buddy.plan import PLAN_COLUMNS, default_plan, row_to_dict


WORKOUT_COLUMNS = (
    "date",
    "exercise_id",
    "exercise",
    "set_number",
    "target_amount",
    "actual_amount",
    "target_unit",
    "weight",
    "weight_unit",
    "logged_at",
)
HEALTH_COLUMNS = (
    "date",
    "walk_jog_minutes",
    "gym_minutes",
    "steps",
    "calories",
    "water_liters",
    "protein_grams",
    "body_weight_kg",
    "waist_cm",
    "notes",
    "gym_attended",
)


class SheetsStore:
    def __init__(self, spreadsheet: gspread.Spreadsheet) -> None:
        self._spreadsheet = spreadsheet
        self._plan = self._ensure_worksheet("WorkoutPlan", PLAN_COLUMNS, 1000)
        if len(self._plan.get_all_values()) <= 1:
            self.save_plan(default_plan())

    @staticmethod
    def _is_blank(values: Sequence[Sequence[str]]) -> bool:
        return not any(cell.strip() for row in values for cell in row)

    def _ensure_worksheet(
        self, title: str, columns: Sequence[str], row_count: int
    ) -> gspread.Worksheet:
        try:
            worksheet = self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(
                title=title, rows=row_count, cols=len(columns)
            )
        values = worksheet.get_all_values()
        if self._is_blank(values):
            worksheet.clear()
            worksheet.update(values=[list(columns)], range_name="A1")
        elif not values[0] or not any(cell.strip() for cell in values[0]):
            raise ValueError(
                f"The {title} worksheet has data but its header row is blank. "
                f"Expected: {', '.join(columns)}."
            )
        elif tuple(cell.strip() for cell in values[0]) != tuple(columns):
            existing_columns = tuple(cell.strip() for cell in values[0])
            if (
                len(existing_columns) < len(columns)
                and existing_columns == tuple(columns[: len(existing_columns)])
            ):
                worksheet.update(values=[list(columns)], range_name="A1")
            else:
                raise ValueError(
                    f"The {title} worksheet has unexpected columns. "
                    f"Expected: {', '.join(columns)}."
                )
        return worksheet

    @staticmethod
    def _year_tab_name(prefix: str, year: int) -> str:
        if year < 1 or year > 9999:
            raise ValueError("Year must be between 1 and 9999.")
        return f"{prefix}_{year:04d}"

    def ensure_year(self, year: int) -> None:
        self._ensure_worksheet(
            self._year_tab_name("WorkoutSets", year), WORKOUT_COLUMNS, 50000
        )
        self._ensure_worksheet(
            self._year_tab_name("DailyHealth", year), HEALTH_COLUMNS, 10000
        )

    def _year_worksheets(
        self, prefix: str, columns: Sequence[str], row_count: int
    ) -> list[gspread.Worksheet]:
        worksheets = []
        for worksheet in self._spreadsheet.worksheets():
            if re.fullmatch(rf"{re.escape(prefix)}_\d{{4}}", worksheet.title):
                worksheets.append(
                    self._ensure_worksheet(worksheet.title, columns, row_count)
                )
        return sorted(worksheets, key=lambda worksheet: worksheet.title)

    @staticmethod
    def _records(worksheet: gspread.Worksheet) -> list[dict[str, Any]]:
        values = worksheet.get_all_values()
        if len(values) < 2:
            return []
        headers = values[0]
        return [
            {
                header: row[index] if index < len(row) else ""
                for index, header in enumerate(headers)
            }
            for row in values[1:]
            if any(cell != "" for cell in row)
        ]

    @staticmethod
    def _row_values(columns: Sequence[str], record: Mapping[str, Any]) -> list[Any]:
        values: list[Any] = []
        for column in columns:
            value = record.get(column, "")
            if isinstance(value, bool):
                value = "TRUE" if value else "FALSE"
            values.append("" if value is None else value)
        return values

    def get_plan(self) -> list[dict[str, Any]]:
        return [row_to_dict(record) for record in self._records(self._plan)]

    def save_plan(self, records: Sequence[Mapping[str, Any]]) -> None:
        values = [list(PLAN_COLUMNS)]
        values.extend(self._row_values(PLAN_COLUMNS, record) for record in records)
        self._plan.clear()
        self._plan.update(values=values, range_name="A1")

    def get_workout_logs(self) -> list[dict[str, Any]]:
        return [
            record
            for worksheet in self._year_worksheets(
                "WorkoutSets", WORKOUT_COLUMNS, 50000
            )
            for record in self._records(worksheet)
        ]

    def get_health_logs(self) -> list[dict[str, Any]]:
        return [
            record
            for worksheet in self._year_worksheets(
                "DailyHealth", HEALTH_COLUMNS, 10000
            )
            for record in self._records(worksheet)
        ]

    @staticmethod
    def _delete_matching_rows(
        worksheet: gspread.Worksheet,
        headers: Sequence[str],
        predicate: Any,
    ) -> None:
        values = worksheet.get_all_values()
        if len(values) < 2:
            return
        positions = {header: index for index, header in enumerate(headers)}
        remove: list[int] = []
        for row_number, row in enumerate(values[1:], start=2):
            record = {
                header: row[index] if index < len(row) else ""
                for index, header in positions.items()
            }
            if predicate(record):
                remove.append(row_number)
        SheetsStore._delete_rows(worksheet, remove)

    @staticmethod
    def _delete_rows(worksheet: gspread.Worksheet, row_numbers: Sequence[int]) -> None:
        ranges: list[tuple[int, int]] = []
        for row_number in sorted(set(row_numbers)):
            if ranges and row_number == ranges[-1][1] + 1:
                ranges[-1] = (ranges[-1][0], row_number)
            else:
                ranges.append((row_number, row_number))
        for start, end in reversed(ranges):
            worksheet.delete_rows(start, end)

    def save_exercise_sets(
        self, log_date: date, exercise: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
    ) -> None:
        worksheet = self._ensure_worksheet(
            self._year_tab_name("WorkoutSets", log_date.year),
            WORKOUT_COLUMNS,
            50000,
        )
        self._delete_matching_rows(
            worksheet,
            WORKOUT_COLUMNS,
            lambda record: record.get("date") == log_date.isoformat()
            and record.get("exercise_id") == exercise["id"],
        )
        if rows:
            values = [
                self._row_values(WORKOUT_COLUMNS, row)
                for row in rows
            ]
            worksheet.append_rows(values, value_input_option="RAW")

    def save_daily_health(self, record: Mapping[str, Any]) -> None:
        log_date = str(record["date"])
        parsed_date = date.fromisoformat(log_date[:10])
        worksheet = self._ensure_worksheet(
            self._year_tab_name("DailyHealth", parsed_date.year),
            HEALTH_COLUMNS,
            10000,
        )
        self._delete_matching_rows(
            worksheet,
            HEALTH_COLUMNS,
            lambda existing: existing.get("date") == log_date,
        )
        worksheet.append_row(
            self._row_values(HEALTH_COLUMNS, record),
            value_input_option="RAW",
        )

def open_store(
    spreadsheet_id: str, service_account_info: Mapping[str, Any]
) -> SheetsStore:
    credentials = Credentials.from_service_account_info(
        dict(service_account_info),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(spreadsheet_id)
    return SheetsStore(spreadsheet)
