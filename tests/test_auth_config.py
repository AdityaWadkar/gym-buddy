import bcrypt
import pytest

from gym_buddy.auth import verify_password
from gym_buddy.config import ConfigurationError, load_password_hash, load_settings


def test_password_verification_checks_bcrypt_hash() -> None:
    password_hash = bcrypt.hashpw(b"temporary-test-password", bcrypt.gensalt(rounds=4))

    assert verify_password("temporary-test-password", password_hash.decode("utf-8"))
    assert not verify_password("wrong-password", password_hash.decode("utf-8"))


def test_plaintext_password_is_rejected_as_configuration() -> None:
    with pytest.raises(ConfigurationError, match="bcrypt hash"):
        load_password_hash(
            secrets={},
            environ={"GYM_BUDDY_PASSWORD_HASH": "not-a-hash"},
        )


def test_settings_use_timezone_and_weight_defaults() -> None:
    settings = load_settings(
        secrets={"GOOGLE_SHEETS_ID": "sheet-id"},
        environ={},
    )

    assert settings.timezone.key == "Asia/Kolkata"
    assert settings.weight_unit == "kg"
    assert settings.weight_increase_percent == 2.5


@pytest.mark.parametrize("configured_unit", ["KG", " kg ", "LB", " lb "])
def test_settings_normalize_weight_unit_case_and_whitespace(
    configured_unit: str,
) -> None:
    settings = load_settings(
        secrets={
            "GOOGLE_SHEETS_ID": "sheet-id",
            "WEIGHT_UNIT": configured_unit,
        },
        environ={},
    )

    assert settings.weight_unit == configured_unit.strip().lower()
