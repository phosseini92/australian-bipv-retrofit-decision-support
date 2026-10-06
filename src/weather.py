"""Locked EPW ingestion and time-series validation for the energy model."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


EXPECTED_EPW_FILENAME = "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
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


def load_epw(path: str | Path) -> WeatherDataset:
    """Read the exact locked EPW and apply only specified physical clipping.

    The function deliberately does not coerce the year. If the locked EPW does
    not already yield the required monotonic index, execution stops rather than
    inventing an unapproved calendar-normalisation rule.
    """

    _, _, pvlib = _runtime()
    source_path = Path(path).resolve()
    if source_path.name != EXPECTED_EPW_FILENAME:
        raise WeatherValidationError(
            f"expected locked EPW filename {EXPECTED_EPW_FILENAME!r}; "
            f"received {source_path.name!r}"
        )
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    data, metadata = pvlib.iotools.read_epw(source_path)
    data = data.copy()
    for column in IRRADIANCE_COLUMNS:
        data[column] = data[column].clip(lower=0.0)
    timestep_hours = validate_weather_frame(data)
    return WeatherDataset(
        data=data,
        metadata=dict(metadata),
        timestep_hours=timestep_hours,
        source_path=source_path,
        source_sha256=file_sha256(source_path),
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_AWAITING_LOCKED_EPW"
