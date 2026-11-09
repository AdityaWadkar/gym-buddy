from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.auth.exceptions import GoogleAuthError

from gym_buddy.auth import verify_password
from gym_buddy.config import (
    ConfigurationError,
    load_password_hash,
    load_service_account_info,
    load_settings,
)
from gym_buddy.plan import DAYS, normalize_plan
from gym_buddy.progression import suggest_weight
from gym_buddy.sheets import SheetsStore, open_store


def _read_streamlit_secrets() -> Mapping[str, Any]:
    secret_paths = st.config.get_option("secrets.files")
    if not any(Path(path).exists() for path in secret_paths):
        return {}
    return dict(st.secrets)


def _login(secrets: Mapping[str, Any]) -> None:
    try:
        password_hash = load_password_hash(secrets, os.environ)
    except ConfigurationError as exc:
        st.error(str(exc))
        st.stop()

    if st.session_state.get("authenticated", False):
        return

    st.caption("Sign in to view and log your training.")
    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        if verify_password(password, password_hash):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("That password did not match.")
    st.stop()


def _parse_optional_number(value: str, label: str) -> float | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number or left blank.") from exc
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number


def _value_text(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return ""
    return str(value)


def _is_missing(value: Any) -> bool:
    return value is None or pd.isna(value) or str(value).strip() == ""


def _today_workout(
    store: SheetsStore,
    today: date,
    timezone: ZoneInfo,
    weight_unit: str,
    increase_percent: float,
) -> None:
    st.header(f"Today's workout · {today.strftime('%A, %B %d')}")
    st.caption(
        "Your plan follows the selected timezone. A shortened session still counts "
        "as showing up; log only the work you actually do."
    )
    plan = [row for row in store.get_plan() if row["day"] == today.strftime("%A")]
    if not plan:
        st.info("There are no exercises planned for today. You can edit the schedule below.")
        return

    mode = st.radio(
        "Session",
        ("Short session", "Full plan"),
        horizontal=True,
        help="Short session shows exercises marked Core in the editable plan.",
    )
    if mode == "Short session":
        plan = [row for row in plan if row["is_core"]]
        if not plan:
            st.info("No exercises are marked Core for today. Choose Full plan or edit the plan.")
            return

    logs = store.get_workout_logs()
    today_logs = [row for row in logs if str(row.get("date", ""))[:10] == today.isoformat()]
    completed_ids = {row["exercise_id"] for row in today_logs}

    st.subheader("Choose an exercise to log")
    categories = list(dict.fromkeys(row["category"] for row in plan))
    for category in categories:
        st.markdown(f"**{category}**")
        category_rows = [row for row in plan if row["category"] == category]
        columns = st.columns(2)
        for index, exercise in enumerate(category_rows):
            status = "Logged" if exercise["id"] in completed_ids else "Log"
            target = (
                f'{exercise["target_sets"]} × {exercise["target_amount"]} '
                f'{exercise["target_unit"]}'
            )
            label = f'{exercise["exercise"]} · {target} · {status}'
            if columns[index % 2].button(
                label,
                key=f'choose-{today.isoformat()}-{exercise["id"]}',
                use_container_width=True,
            ):
                st.session_state["active_exercise_id"] = exercise["id"]

    selected_id = st.session_state.get("active_exercise_id")
    exercise = next((row for row in plan if row["id"] == selected_id), None)
    if exercise is None:
        return

    exercise_logs = [
        row for row in logs if row.get("exercise_id") == exercise["id"]
    ]
    suggestion = suggest_weight(
        exercise_logs,
        exercise["target_sets"],
        exercise["target_amount"],
        exercise["target_unit"],
        weight_unit,
        increase_percent,
    )
    st.divider()
    st.subheader(f'Log: {exercise["exercise"]}')
    st.caption(
        f'Target: {exercise["target_sets"]} sets × '
        f'{exercise["target_amount"]} {exercise["target_unit"]}'
    )
    st.info(suggestion["status"])
    if suggestion["weight"] is not None:
        st.write(f'Weight reference: **{suggestion["weight"]:g} {weight_unit}** per set')

    existing_today = sorted(
        (
            row
            for row in today_logs
            if row.get("exercise_id") == exercise["id"]
        ),
        key=lambda row: int(float(row.get("set_number") or 0)),
    )
    previous_by_set = {
        int(float(row["set_number"])): row for row in existing_today
    }
    set_count = st.number_input(
        "Sets completed",
        min_value=1,
        max_value=30,
        value=min(30, max(exercise["target_sets"], len(existing_today))),
        step=1,
        key=f'set-count-{today.isoformat()}-{exercise["id"]}',
    )
    initial_rows = []
    for set_number in range(1, int(set_count) + 1):
        previous = previous_by_set.get(set_number, {})
        initial_rows.append(
            {
                "Set": set_number,
                "Target": f'{exercise["target_amount"]} {exercise["target_unit"]}',
                "Actual amount": (
                    float(previous["actual_amount"])
                    if previous.get("actual_amount") not in (None, "")
                    else None
                ),
                "Weight": (
                    float(previous["weight"])
                    if previous.get("weight") not in (None, "")
                    else suggestion["weight"]
                ),
            }
        )

    with st.form(f'log-{today.isoformat()}-{exercise["id"]}'):
        values = st.data_editor(
            pd.DataFrame(initial_rows),
            hide_index=True,
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "Set": st.column_config.NumberColumn(disabled=True),
                "Target": st.column_config.TextColumn(disabled=True),
                "Actual amount": st.column_config.NumberColumn(
                    min_value=0,
                    step=1,
                    help=f'Enter actual {exercise["target_unit"]} completed.',
                ),
                "Weight": st.column_config.NumberColumn(
                    min_value=0,
                    step=0.5 if weight_unit == "kg" else 2.5,
                    help=f"Enter weight in {weight_unit}; leave blank for unweighted work.",
                ),
            },
        )
        submitted = st.form_submit_button("Save exercise")

    if submitted:
        rows_to_save = []
        errors: list[str] = []
        for _, row in values.iterrows():
            actual = row["Actual amount"]
            weight = row["Weight"]
            if _is_missing(actual):
                if not _is_missing(weight) and exercise["weighted"]:
                    errors.append(f'Set {int(row["Set"])} has a weight but no actual amount.')
                continue
            if float(actual) < 0:
                errors.append(f'Set {int(row["Set"])} amount cannot be negative.')
                continue
            if exercise["weighted"] and _is_missing(weight):
                errors.append(f'Set {int(row["Set"])} needs a weight.')
                continue
            rows_to_save.append(
                {
                    "date": today.isoformat(),
                    "exercise_id": exercise["id"],
                    "exercise": exercise["exercise"],
                    "set_number": int(row["Set"]),
                    "target_amount": exercise["target_amount"],
                    "actual_amount": float(actual),
                    "target_unit": exercise["target_unit"],
                    "weight": None if _is_missing(weight) else float(weight),
                    "weight_unit": weight_unit if not _is_missing(weight) else "",
                    "logged_at": datetime.now(timezone).isoformat(timespec="seconds"),
                }
            )
        if errors:
            for error in errors:
                st.error(error)
        elif not rows_to_save:
            st.warning("Enter at least one set before saving.")
        else:
            store.save_exercise_sets(today, exercise, rows_to_save)
            st.session_state.pop("active_exercise_id", None)
            st.success("Exercise saved.")
            st.rerun()


def _daily_health(store: SheetsStore, today: date) -> None:
    st.header(f"Daily health · {today.strftime('%A, %B %d')}")
    existing = next(
        (
            row
            for row in store.get_health_logs()
            if str(row.get("date", ""))[:10] == today.isoformat()
        ),
        {},
    )
    fields = (
        ("walk_jog_minutes", "Morning walk/jog (minutes)"),
        ("gym_minutes", "Gym duration (minutes)"),
        ("steps", "Steps"),
        ("calories", "Calories consumed (kcal)"),
        ("water_liters", "Water (litres)"),
        ("protein_grams", "Protein estimate (grams, optional)"),
        ("body_weight_kg", "Body weight (kg, optional weekly check-in)"),
        ("waist_cm", "Waist measurement (cm, optional monthly check-in)"),
    )
    existing_attendance = str(existing.get("gym_attended", "")).strip().lower()
    attendance_options = ("Not recorded", "Yes", "No")
    current_attendance = (
        "Yes"
        if existing_attendance in {"true", "yes", "1"}
        else "No"
        if existing_attendance in {"false", "no", "0"}
        else "Not recorded"
    )
    with st.form("daily_health_form"):
        gym_attendance = st.selectbox(
            "Did you go to the gym today?",
            attendance_options,
            index=attendance_options.index(current_attendance),
            help="Choose No if the gym was closed or you did not go. You can still log your other health metrics.",
        )
        values = {
            key: st.text_input(label, value=_value_text(existing.get(key)))
            for key, label in fields
        }
        notes = st.text_input("Notes (optional)", value=_value_text(existing.get("notes")))
        submitted = st.form_submit_button("Save daily health log")
    if not submitted:
        return

    try:
        parsed = {
            key: _parse_optional_number(values[key], label)
            for key, label in fields
        }
    except ValueError as exc:
        st.error(str(exc))
        return
    attendance_value = (
        True if gym_attendance == "Yes" else False if gym_attendance == "No" else None
    )
    record = {
        "date": today.isoformat(),
        **parsed,
        "notes": notes.strip(),
        "gym_attended": attendance_value,
    }
    store.save_daily_health(record)
    st.success("Daily health log saved.")


def _weekly_report(store: SheetsStore, today: date) -> None:
    st.header("Weekly health report")
    start = today - timedelta(days=6)
    health = [
        row
        for row in store.get_health_logs()
        if start.isoformat() <= str(row.get("date", ""))[:10] <= today.isoformat()
    ]
    workouts = [
        row
        for row in store.get_workout_logs()
        if start.isoformat() <= str(row.get("date", ""))[:10] <= today.isoformat()
    ]
    logged_days = len({str(row.get("date", ""))[:10] for row in workouts})
    attendance_by_date = {
        str(row.get("date", ""))[:10]: str(row.get("gym_attended", "")).strip().lower()
        for row in health
        if str(row.get("gym_attended", "")).strip()
    }
    attended_days = sum(value in {"true", "yes", "1"} for value in attendance_by_date.values())
    did_not_attend_days = sum(
        value in {"false", "no", "0"} for value in attendance_by_date.values()
    )
    cardio_minutes = sum(
        float(row["walk_jog_minutes"])
        for row in health
        if str(row.get("walk_jog_minutes", "")).strip()
    )
    gym_minutes = sum(
        float(row["gym_minutes"])
        for row in health
        if str(row.get("gym_minutes", "")).strip()
    )
    steps = sum(
        float(row["steps"])
        for row in health
        if str(row.get("steps", "")).strip()
    )
    calories = sum(
        float(row["calories"])
        for row in health
        if str(row.get("calories", "")).strip()
    )
    sets_logged = len(workouts)
    average_water_values = [
        float(row["water_liters"])
        for row in health
        if str(row.get("water_liters", "")).strip()
    ]
    average_water = (
        sum(average_water_values) / len(average_water_values)
        if average_water_values
        else None
    )
    protein_values = [
        float(row["protein_grams"])
        for row in health
        if str(row.get("protein_grams", "")).strip()
    ]
    average_protein = (
        sum(protein_values) / len(protein_values) if protein_values else None
    )

    activity_metrics = st.columns(6)
    activity_metrics[0].metric("Exercise days logged", logged_days)
    activity_metrics[1].metric("Gym attendance: yes", attended_days)
    activity_metrics[2].metric("Gym attendance: no", did_not_attend_days)
    activity_metrics[3].metric("Sets logged", sets_logged)
    activity_metrics[4].metric("Morning walk/jog", f"{cardio_minutes:g} min")
    activity_metrics[5].metric("Gym duration", f"{gym_minutes:g} min")
    health_metrics = st.columns(4)
    health_metrics[0].metric("Steps", f"{steps:,.0f}")
    health_metrics[1].metric("Calories consumed", f"{calories:,.0f} kcal")
    health_metrics[2].metric(
        "Avg. water",
        f"{average_water:.2f} L/day" if average_water is not None else "—",
    )
    health_metrics[3].metric(
        "Avg. protein",
        f"{average_protein:.0f} g/day" if average_protein is not None else "—",
    )

    if not health and not workouts:
        st.info("Log workouts or daily health data to start your weekly summary.")
        return

    frame = pd.DataFrame(health)
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        for field in ("body_weight_kg", "waist_cm"):
            if field in frame:
                frame[field] = pd.to_numeric(frame[field], errors="coerce")
        if frame.get("body_weight_kg", pd.Series(dtype=float)).notna().any():
            st.subheader("Optional body measurement trends")
            st.markdown("**Body weight (kg)**")
            st.line_chart(frame.set_index("date")[["body_weight_kg"]].dropna())
        if frame.get("waist_cm", pd.Series(dtype=float)).notna().any():
            st.markdown("**Waist (cm)**")
            st.line_chart(frame.set_index("date")[["waist_cm"]].dropna())
    st.caption(
        "These summaries show your logged trends; they are not medical advice or a diagnosis."
    )

    st.subheader("Year-by-year comparison")
    all_health = pd.DataFrame(store.get_health_logs())
    all_workouts = pd.DataFrame(store.get_workout_logs())
    if all_health.empty and all_workouts.empty:
        st.info("Yearly comparisons will appear after you have logged activity.")
        return

    for frame in (all_health, all_workouts):
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame.dropna(subset=["date"], inplace=True)

    years = set()
    if not all_health.empty:
        years.update(all_health["date"].dt.year.astype(int).tolist())
    if not all_workouts.empty:
        years.update(all_workouts["date"].dt.year.astype(int).tolist())

    yearly_rows = []
    for year in sorted(years):
        health_year = (
            all_health[all_health["date"].dt.year == year]
            if not all_health.empty
            else pd.DataFrame()
        )
        workout_year = (
            all_workouts[all_workouts["date"].dt.year == year]
            if not all_workouts.empty
            else pd.DataFrame()
        )

        def total(frame: pd.DataFrame, column: str) -> float:
            if frame.empty or column not in frame:
                return 0
            return pd.to_numeric(frame[column], errors="coerce").sum()

        protein_values = (
            pd.to_numeric(health_year["protein_grams"], errors="coerce").dropna()
            if not health_year.empty and "protein_grams" in health_year
            else pd.Series(dtype=float)
        )
        weights = (
            health_year[["date", "body_weight_kg"]].copy()
            if not health_year.empty and "body_weight_kg" in health_year
            else pd.DataFrame()
        )
        if not weights.empty:
            weights["body_weight_kg"] = pd.to_numeric(
                weights["body_weight_kg"], errors="coerce"
            )
            weights = weights.dropna(subset=["body_weight_kg"]).sort_values("date")
        weight_change = (
            float(weights["body_weight_kg"].iloc[-1] - weights["body_weight_kg"].iloc[0])
            if len(weights) > 1
            else None
        )
        yearly_rows.append(
            {
                "Year": year,
                "Exercise days logged": (
                    int(workout_year["date"].dt.date.nunique())
                    if not workout_year.empty
                    else 0
                ),
                "Gym attendance yes": (
                    int(
                        health_year.loc[
                            health_year["gym_attended"]
                            .astype(str)
                            .str.strip()
                            .str.lower()
                            .isin({"true", "yes", "1"}),
                            "date",
                        ]
                        .dt.date.nunique()
                    )
                    if not health_year.empty and "gym_attended" in health_year
                    else 0
                ),
                "Gym attendance no": (
                    int(
                        health_year.loc[
                            health_year["gym_attended"]
                            .astype(str)
                            .str.strip()
                            .str.lower()
                            .isin({"false", "no", "0"}),
                            "date",
                        ]
                        .dt.date.nunique()
                    )
                    if not health_year.empty and "gym_attended" in health_year
                    else 0
                ),
                "Sets logged": len(workout_year),
                "Walk/jog minutes": total(health_year, "walk_jog_minutes"),
                "Gym minutes": total(health_year, "gym_minutes"),
                "Steps": total(health_year, "steps"),
                "Calories logged": total(health_year, "calories"),
                "Avg. protein (g/day logged)": (
                    round(float(protein_values.mean()), 1)
                    if not protein_values.empty
                    else None
                ),
                "Weight change (kg)": (
                    round(weight_change, 1) if weight_change is not None else None
                ),
            }
        )
    st.dataframe(pd.DataFrame(yearly_rows), hide_index=True, use_container_width=True)

    if not all_health.empty:
        monthly = all_health.copy()
        monthly["walk_jog_minutes"] = pd.to_numeric(
            monthly.get("walk_jog_minutes", 0), errors="coerce"
        ).fillna(0)
        monthly["gym_minutes"] = pd.to_numeric(
            monthly.get("gym_minutes", 0), errors="coerce"
        ).fillna(0)
        monthly["Training minutes"] = (
            monthly["walk_jog_minutes"] + monthly["gym_minutes"]
        )
        monthly["Month"] = monthly["date"].dt.to_period("M").dt.to_timestamp()
        monthly["Year"] = monthly["date"].dt.year.astype(str)
        monthly_summary = monthly.groupby(["Month", "Year"])[
            "Training minutes"
        ].sum().unstack("Year")
        if not monthly_summary.empty:
            st.markdown("**Monthly walk/jog + gym minutes by year**")
            st.line_chart(monthly_summary)


def _edit_plan(store: SheetsStore) -> None:
    st.header("Edit weekly plan")
    st.caption(
        "The initial exercises and set/rep targets came from your image. "
        "Starting weights were not listed, so those are learned from your logs."
    )
    plan = store.get_plan()
    frame = pd.DataFrame(plan)
    if frame.empty:
        frame = pd.DataFrame(columns=("id", *[column for column in plan if column != "id"]))
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "day": st.column_config.SelectboxColumn("Day", options=DAYS),
            "target_sets": st.column_config.NumberColumn(min_value=1, step=1),
            "weighted": st.column_config.CheckboxColumn(),
            "is_core": st.column_config.CheckboxColumn(),
        },
    )
    if st.button("Save weekly plan", type="primary"):
        try:
            cleaned = normalize_plan(edited.to_dict(orient="records"))
        except ValueError as exc:
            st.error(str(exc))
            return
        store.save_plan(cleaned)
        st.success("Weekly plan saved.")
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Gym Buddy", page_icon="🏋️", layout="wide")
    load_dotenv()
    st.title("Gym Buddy")
    secrets = _read_streamlit_secrets()
    _login(secrets)
    if st.sidebar.button("Log out"):
        st.session_state.pop("authenticated", None)
        st.session_state.pop("active_exercise_id", None)
        st.session_state.pop("_sheets_store", None)
        st.session_state.pop("_sheets_store_key", None)
        st.rerun()

    try:
        settings = load_settings(secrets, os.environ)
        account_info = load_service_account_info(secrets, os.environ)
    except ConfigurationError as exc:
        st.error(str(exc))
        st.info("See README.md for local setup and Streamlit deployment instructions.")
        st.stop()

    try:
        local_today = datetime.now(settings.timezone).date()
        store_key = (settings.spreadsheet_id, account_info["client_email"])
        if st.session_state.get("_sheets_store_key") != store_key:
            st.session_state["_sheets_store"] = open_store(
                settings.spreadsheet_id, account_info
            )
            st.session_state["_sheets_store_key"] = store_key
        store = st.session_state["_sheets_store"]
        store.ensure_year(local_today.year)
    except PermissionError as exc:
        cause = exc.__cause__
        detail = str(cause) if cause is not None else str(exc)
        st.error(f"Google Sheets denied access: {detail or 'permission denied'}")
        st.info(
            "Enable the Google Sheets API in the Google Cloud project used by this "
            "service account. Then wait a few minutes and restart the app. Also "
            "confirm that the spreadsheet is shared with the service account's "
            "client_email as an Editor."
        )
        st.stop()
    except (gspread.exceptions.GSpreadException, GoogleAuthError, ValueError) as exc:
        st.error(f"Could not access or prepare Google Sheets: {exc}")
        st.info(
            "Check the spreadsheet ID, service-account credentials, sharing access, "
            "and worksheet headers."
        )
        st.stop()
    st.caption(f"Today is {local_today.strftime('%A')} · timezone: {settings.timezone.key}")
    workout_tab, health_tab, report_tab, plan_tab = st.tabs(
        ("Today's workout", "Daily health", "Weekly report", "Edit plan")
    )
    with workout_tab:
        _today_workout(
            store,
            local_today,
            settings.timezone,
            settings.weight_unit,
            settings.weight_increase_percent,
        )
    with health_tab:
        _daily_health(store, local_today)
    with report_tab:
        _weekly_report(store, local_today)
    with plan_tab:
        _edit_plan(store)


if __name__ == "__main__":
    main()
