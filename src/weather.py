"""Locked EPW ingestion and time-series validation for the energy model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEATHER_MANIFEST_PATH = PROJECT_ROOT / "data" / "weather" / "weather_manifest.json"
REQUIRED_WEATHER_COLUMNS = ("temp_air", "wind_speed", "ghi", "dni", "dhi")
IRRADIANCE_COLUMNS = ("ghi", "dni", "dhi")
EXPECTED_HOURS = 8760


class WeatherValidationError(ValueError):
    """Raised when weather data violate the locked analysis contract."""


@dataclass(frozen=True)
class WeatherDataset:
    data: Any
    metadata: dict[str, Any]
    timestep_hours: float
    source_path: Path
    source_sha256: str
    source_index: Any | None = None
    normalization: dict[str, Any] = field(default_factory=dict)


def load_weather_manifest() -> dict[str, Any]:
    with WEATHER_MANIFEST_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def _runtime():
    try:
        import numpy as np
        import pandas as pd
        import pvlib
    except ImportError as exc:  # pragma: no cover - exercised only before setup
        raise RuntimeError(
            "The energy runtime is not installed. Install requirements.txt first."
        ) from exc
    return np, pd, pvlib


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_weather_frame(data: Any, *, expected_hours: int = EXPECTED_HOURS) -> float:
    """Validate the locked hourly weather contract and return timestep hours."""

    np, pd, _ = _runtime()
    missing = set(REQUIRED_WEATHER_COLUMNS) - set(data.columns)
    if missing:
        raise WeatherValidationError(f"weather columns missing: {sorted(missing)}")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise WeatherValidationError("weather index must be a pandas DatetimeIndex")
    if data.index.tz is None:
        raise WeatherValidationError("weather index must be timezone-aware")
    if not data.index.is_monotonic_increasing or not data.index.is_unique:
        raise WeatherValidationError("weather index must be monotonic and unique")
    if len(data) != expected_hours:
        raise WeatherValidationError(
            f"weather file must contain {expected_hours} hourly records; found {len(data)}"
        )
    if data[list(REQUIRED_WEATHER_COLUMNS)].isna().any().any():
        raise WeatherValidationError("weather inputs contain missing values")
    if not np.isfinite(data[list(REQUIRED_WEATHER_COLUMNS)].to_numpy(dtype=float)).all():
        raise WeatherValidationError("weather inputs contain non-finite values")

    deltas = data.index.to_series().diff().dropna().dt.total_seconds().to_numpy()
    if len(deltas) == 0 or not np.allclose(deltas, deltas[0], rtol=0.0, atol=1e-9):
        raise WeatherValidationError("weather timestep must be constant")
    timestep_hours = float(deltas[0] / 3600.0)
    if abs(timestep_hours - 1.0) > 1e-12:
        raise WeatherValidationError(
            f"locked weather file must be hourly; found {timestep_hours:g} h"
        )
    return timestep_hours


def normalize_tmy_index(
    data: Any,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
):
    """Replace mixed source years with the approved non-leap audit calendar."""

    np, pd, _ = _runtime()
    raw_index = data.index.copy()
    if not isinstance(raw_index, pd.DatetimeIndex) or raw_index.tz is None:
        raise WeatherValidationError("raw EPW index must be timezone-aware")
    if len(raw_index) != EXPECTED_HOURS or not raw_index.is_unique:
        raise WeatherValidationError("raw EPW must contain 8760 unique timestamps")

    rule = manifest["index_normalization"]
    target_year = int(rule["target_year"])
    if target_year % 4 == 0 and (target_year % 100 != 0 or target_year % 400 == 0):
        raise WeatherValidationError("normalization target year must be non-leap")

    offset_hours = float(metadata["TZ"])
    expected_offset = float(manifest["station"]["timezone_utc_offset_hours"])
    if offset_hours != expected_offset:
        raise WeatherValidationError(
            f"EPW timezone {offset_hours:g} does not match manifest {expected_offset:g}"
        )
    fixed_timezone = timezone(timedelta(hours=offset_hours))
    normalized_index = pd.date_range(
        start=pd.Timestamp(target_year, 1, 1, 0, tz=fixed_timezone),
        periods=EXPECTED_HOURS,
        freq="h",
    )

    raw_calendar = np.column_stack(
        (raw_index.month, raw_index.day, raw_index.hour, raw_index.minute)
    )
    normalized_calendar = np.column_stack(
        (
            normalized_index.month,
            normalized_index.day,
            normalized_index.hour,
            normalized_index.minute,
        )
    )
    if not np.array_equal(raw_calendar, normalized_calendar):
        raise WeatherValidationError(
            "raw EPW month/day/hour sequence does not match a complete non-leap year"
        )

    observed_month_years: dict[str, int] = {}
    for month in range(1, 13):
        years = sorted(set(raw_index[raw_index.month == month].year))
        if len(years) != 1:
            raise WeatherValidationError(
                f"month {month:02d} must map to exactly one TMY source year"
            )
        observed_month_years[f"{month:02d}"] = int(years[0])
    expected_month_years = {
        key: int(value) for key, value in manifest["source_year_by_month"].items()
    }
    if observed_month_years != expected_month_years:
        raise WeatherValidationError("EPW source-year mapping does not match manifest")

    normalized = data.copy()
    normalized.index = normalized_index
    normalization = {
        "rule": rule["rule"],
        "target_year": target_year,
        "timezone": str(normalized_index.tz),
        "raw_index_monotonic": bool(raw_index.is_monotonic_increasing),
        "raw_index_unique": bool(raw_index.is_unique),
        "source_year_by_month": observed_month_years,
    }
    return normalized, raw_index, normalization


def load_epw(path: str | Path) -> WeatherDataset:
    """Read the exact locked EPW and apply only specified physical clipping.

    The function deliberately does not coerce the year. If the locked EPW does
    not already yield the required monotonic index, execution stops rather than
    inventing an unapproved calendar-normalisation rule.
    """

    _, _, pvlib = _runtime()
    manifest = load_weather_manifest()
    source_path = Path(path).resolve()
    expected_filename = manifest["filename"]
    if source_path.name != expected_filename:
        raise WeatherValidationError(
            f"expected locked EPW filename {expected_filename!r}; "
            f"received {source_path.name!r}"
        )
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    source_hash = file_sha256(source_path)
    if source_hash != manifest["sha256"]:
        raise WeatherValidationError(
            f"locked EPW hash mismatch: expected {manifest['sha256']}, found {source_hash}"
        )
    if source_path.stat().st_size != int(manifest["size_bytes"]):
        raise WeatherValidationError("locked EPW size does not match weather manifest")

    data, metadata = pvlib.iotools.read_epw(source_path)
    expected_station = manifest["station"]
    metadata_checks = {
        "city": expected_station["name"],
        "state-prov": expected_station["region"],
        "country": expected_station["country"],
        "WMO_code": expected_station["wmo"],
        "latitude": expected_station["latitude"],
        "longitude": expected_station["longitude"],
        "TZ": expected_station["timezone_utc_offset_hours"],
        "altitude": expected_station["elevation_m"],
    }
    for key, expected in metadata_checks.items():
        observed = metadata.get(key)
        if isinstance(expected, float):
            if abs(float(observed) - expected) > 1e-9:
                raise WeatherValidationError(
                    f"EPW metadata mismatch for {key}: expected {expected}, found {observed}"
                )
        elif str(observed) != str(expected):
            raise WeatherValidationError(
                f"EPW metadata mismatch for {key}: expected {expected}, found {observed}"
            )

    data, source_index, normalization = normalize_tmy_index(data, metadata, manifest)
    data = data.copy()
    for column in IRRADIANCE_COLUMNS:
        data[column] = data[column].clip(lower=0.0)
    timestep_hours = validate_weather_frame(data)
    return WeatherDataset(
        data=data,
        metadata=dict(metadata),
        timestep_hours=timestep_hours,
        source_path=source_path,
        source_sha256=source_hash,
        source_index=source_index,
        normalization=normalization,
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_CONTROLLED_EPW_VALIDATED"
