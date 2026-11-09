from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigurationError(ValueError):
    """Raised when required app configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str
    timezone: ZoneInfo
    weight_unit: str
    weight_increase_percent: float


def _read_value(
    name: str,
    secrets: Mapping[str, Any],
    environ: Mapping[str, str],
    default: str | None = None,
) -> str | None:
    value = environ.get(name)
    if value:
        return value
    secret_value = secrets.get(name)
    if secret_value is not None and str(secret_value):
        return str(secret_value)
    return default


def load_password_hash(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    values = secrets if secrets is not None else {}
    variables = environ if environ is not None else os.environ
    password_hash = _read_value("GYM_BUDDY_PASSWORD_HASH", values, variables)
    if not password_hash:
        raise ConfigurationError(
            "GYM_BUDDY_PASSWORD_HASH is not configured. Generate a bcrypt hash "
            "with `python utils/generate_password_hash.py` and add it to .env "
            "or Streamlit secrets."
        )
    if not password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        raise ConfigurationError(
            "GYM_BUDDY_PASSWORD_HASH must be a bcrypt hash, not a plaintext password."
        )
    return password_hash


def load_settings(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    values = secrets if secrets is not None else {}
    variables = environ if environ is not None else os.environ

    spreadsheet_id = _read_value("GOOGLE_SHEETS_ID", values, variables)
    if not spreadsheet_id:
        raise ConfigurationError("GOOGLE_SHEETS_ID is not configured.")

    timezone_name = _read_value(
        "APP_TIMEZONE", values, variables, default="Asia/Kolkata"
    )
    try:
        timezone = ZoneInfo(timezone_name or "Asia/Kolkata")
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"Unknown APP_TIMEZONE: {timezone_name}") from exc

    weight_unit = (
        _read_value("WEIGHT_UNIT", values, variables, default="kg") or "kg"
    ).strip().lower()
    if weight_unit not in {"kg", "lb"}:
        raise ConfigurationError("WEIGHT_UNIT must be either 'kg' or 'lb'.")

    raw_percent = _read_value(
        "WEIGHT_INCREASE_PERCENT", values, variables, default="2.5"
    )
    try:
        weight_increase_percent = float(raw_percent or "2.5")
    except ValueError as exc:
        raise ConfigurationError(
            "WEIGHT_INCREASE_PERCENT must be a positive number."
        ) from exc
    if weight_increase_percent <= 0:
        raise ConfigurationError("WEIGHT_INCREASE_PERCENT must be a positive number.")

    return Settings(
        spreadsheet_id=spreadsheet_id,
        timezone=timezone,
        weight_unit=weight_unit,
        weight_increase_percent=weight_increase_percent,
    )


def load_service_account_info(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    values = secrets if secrets is not None else {}
    variables = environ if environ is not None else os.environ
    raw_credentials = _read_value(
        "GOOGLE_SERVICE_ACCOUNT_JSON", values, variables
    )
    if raw_credentials:
        try:
            credentials = json.loads(raw_credentials)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                "GOOGLE_SERVICE_ACCOUNT_JSON must contain valid JSON."
            ) from exc
    else:
        credentials = values.get("gcp_service_account")

    if not isinstance(credentials, Mapping):
        raise ConfigurationError(
            "Google service-account credentials are missing. Configure "
            "GOOGLE_SERVICE_ACCOUNT_JSON locally or [gcp_service_account] in "
            "Streamlit secrets."
        )
    required_keys = {"client_email", "private_key", "token_uri"}
    missing_keys = sorted(required_keys.difference(credentials.keys()))
    if missing_keys:
        raise ConfigurationError(
            "Google service-account credentials are missing: "
            + ", ".join(missing_keys)
        )
    return dict(credentials)
