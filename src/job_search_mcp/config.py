"""Local settings: personal parameters read from a TOML file, with generic defaults.

The file path comes from JOB_SEARCH_CONFIG. Without the variable, or when the file does not
exist, the defaults apply. The domain never reads this file: it receives the values.
"""

import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from job_search_mcp import domain
from job_search_mcp.db import to_date

CONFIG_ENV_VAR = "JOB_SEARCH_CONFIG"


class ConfigError(Exception):
    """The settings file exists but cannot be used: invalid TOML, unknown key or wrong type."""


@dataclass(frozen=True)
class Settings:
    """Personal parameters of the job search. None means "not set"."""

    job_follow_up_days: int = domain.JOB_FOLLOW_UP_DAYS
    contact_follow_up_days: int = domain.CONTACT_FOLLOW_UP_DAYS
    deadline: date | None = None
    applications_per_week: int | None = None
    interview_rate: float | None = None
    proposal_ttl_hours: int = 24


DEFAULT_SETTINGS = Settings()


def _int_up_to(maximum: int):
    """Converter for an integer from 1 to `maximum` (the cap keeps date arithmetic in range)."""

    def convert(value) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"use an integer from 1 to {maximum}")
        return value

    return convert


MAX_DAYS = 365
MAX_TTL_HOURS = 720
MAX_APPLICATIONS_PER_WEEK = 1000


def _rate(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("use a number from 0 to 1")
    return float(value)


def _deadline(value) -> date:
    try:
        return to_date(value)
    except (ValueError, TypeError):
        raise ValueError("use a date (YYYY-MM-DD)") from None


# Section -> key in the file -> (field of Settings, converter that validates the value).
SCHEMA = {
    "follow_up": {
        "job_days": ("job_follow_up_days", _int_up_to(MAX_DAYS)),
        "contact_days": ("contact_follow_up_days", _int_up_to(MAX_DAYS)),
    },
    "goals": {
        "deadline": ("deadline", _deadline),
        "applications_per_week": (
            "applications_per_week",
            _int_up_to(MAX_APPLICATIONS_PER_WEEK),
        ),
        "interview_rate": ("interview_rate", _rate),
    },
    "proposals": {
        "ttl_hours": ("proposal_ttl_hours", _int_up_to(MAX_TTL_HOURS)),
    },
}


def config_path() -> Path | None:
    """Return the settings path from JOB_SEARCH_CONFIG, or None when it is not set."""
    value = os.environ.get(CONFIG_ENV_VAR)
    return Path(value) if value else None


def load_settings(path: str | Path | None = None) -> Settings:
    """Read the settings file (default: JOB_SEARCH_CONFIG) and return the settings.

    No path or a missing file gives the defaults. Invalid TOML, an unknown section or key,
    or a value of the wrong type raises ConfigError with a message for the user.
    """
    path = Path(path) if path is not None else config_path()
    if path is None or not path.is_file():
        return DEFAULT_SETTINGS
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as failure:
        raise ConfigError(f"Invalid settings file {path}: {failure}.") from None
    except UnicodeDecodeError:
        raise ConfigError(
            f"Invalid settings file {path}: it is not UTF-8 text. Save it with UTF-8 encoding."
        ) from None
    except OSError as failure:
        raise ConfigError(f"Could not read the settings file {path}: {failure}.") from None

    values = {}
    for section, content in data.items():
        keys = SCHEMA.get(section)
        if keys is None:
            raise ConfigError(
                f"Unknown section [{section}] in {path}. Valid sections: {', '.join(SCHEMA)}."
            )
        if not isinstance(content, dict):
            raise ConfigError(f"'{section}' in {path} must be a section ([{section}]).")
        for key, value in content.items():
            if key not in keys:
                raise ConfigError(
                    f"Unknown key '{section}.{key}' in {path}. Valid keys: {', '.join(keys)}."
                )
            field, convert = keys[key]
            try:
                values[field] = convert(value)
            except ValueError as failure:
                raise ConfigError(
                    f"Invalid value for '{section}.{key}' in {path}: {value!r} ({failure})."
                ) from None
    return Settings(**values)
