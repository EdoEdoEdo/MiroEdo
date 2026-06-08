"""Volume forecast (Fase C) — pure-numpy time-series forecast.

Avoids heavy deps (statsmodels/prophet). Implements:
  * weekly aggregation of seed.timeline
  * Holt linear smoothing (level + trend) when ≥4 weeks available
  * Naive mean fallback otherwise
  * Symmetric 95% CI from residual std (z=1.96)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Sequence

from app.schemas import BrandSeed, ForecastPoint, TimelineEvent, VolumeForecast


def forecast_volume(
    seed: BrandSeed,
    *,
    horizon_weeks: int = 4,
) -> VolumeForecast:
    """Forecast weekly mention volume.

    Prefers `seed.volume_series_weekly` (autoritative, populated by LLM
    extractor from explicit weekly volume tables). Falls back to
    `seed.timeline` when the dedicated series is empty (CSV path, or
    documents without a volume table).
    """
    source_series = seed.volume_series_weekly or seed.timeline
    weekly = _aggregate_weekly(source_series)
    history_points = _to_history_points(weekly)
    if len(weekly) < 2:
        return VolumeForecast(
            method="insufficient_data",
            history_weeks=len(weekly),
            horizon_weeks=horizon_weeks,
            historical=history_points,
            forecast=[],
            notes="Almeno 2 settimane di storico sono richieste per generare un forecast.",
        )
    if len(weekly) < 4:
        return _naive_mean_forecast(weekly, history_points, horizon_weeks)
    return _holt_forecast(weekly, history_points, horizon_weeks)


# ----------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------


def _aggregate_weekly(timeline: Sequence[TimelineEvent]) -> list[tuple[datetime, float]]:
    """Return sorted [(monday_dt, mentions), ...] aggregated per ISO week.

    The seed.timeline produced by tabular_adapter already buckets per week, but
    we re-aggregate defensively in case daily events are present.
    """
    buckets: dict[datetime, float] = {}
    for ev in timeline:
        try:
            dt = datetime.fromisoformat(ev.date[:10])
        except (ValueError, TypeError):
            continue
        monday = dt - timedelta(days=dt.weekday())
        buckets[monday] = buckets.get(monday, 0.0) + float(ev.mentions)
    return sorted(buckets.items())


def _to_history_points(weekly: list[tuple[datetime, float]]) -> list[ForecastPoint]:
    return [
        ForecastPoint(
            date=monday.date().isoformat(),
            yhat=v,
            yhat_lower=v,
            yhat_upper=v,
        )
        for monday, v in weekly
    ]


# ----------------------------------------------------------------------
# Forecasts
# ----------------------------------------------------------------------


def _naive_mean_forecast(
    weekly: list[tuple[datetime, float]],
    history_points: list[ForecastPoint],
    horizon_weeks: int,
) -> VolumeForecast:
    values = [v for _, v in weekly]
    mean = sum(values) / len(values)
    std = _std(values, mean)
    band = 1.96 * std
    last_monday = weekly[-1][0]
    fc = []
    for i in range(1, horizon_weeks + 1):
        d = (last_monday + timedelta(weeks=i)).date().isoformat()
        fc.append(
            ForecastPoint(
                date=d,
                yhat=mean,
                yhat_lower=max(0.0, mean - band),
                yhat_upper=mean + band,
            )
        )
    return VolumeForecast(
        method="naive_mean",
        history_weeks=len(weekly),
        horizon_weeks=horizon_weeks,
        historical=history_points,
        forecast=fc,
        notes=(
            f"Forecast naive (media={mean:.1f}, std={std:.1f}). "
            "Servono ≥4 settimane per attivare Holt smoothing."
        ),
    )


def _holt_forecast(
    weekly: list[tuple[datetime, float]],
    history_points: list[ForecastPoint],
    horizon_weeks: int,
) -> VolumeForecast:
    """Holt linear (additive trend) with fixed smoothing alpha=0.5, beta=0.3."""
    values = [v for _, v in weekly]
    alpha, beta = 0.5, 0.3

    level = values[0]
    trend = values[1] - values[0]
    fitted = [level]
    for v in values[1:]:
        prev_level = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
        fitted.append(level)

    # in-sample residuals (skip first)
    residuals = [values[i] - fitted[i] for i in range(1, len(values))]
    rmean = sum(residuals) / len(residuals)
    rstd = _std(residuals, rmean)
    band_base = 1.96 * rstd

    last_monday = weekly[-1][0]
    fc = []
    for i in range(1, horizon_weeks + 1):
        yhat = level + i * trend
        # widening CI: scale by sqrt(i)
        band = band_base * math.sqrt(i)
        d = (last_monday + timedelta(weeks=i)).date().isoformat()
        fc.append(
            ForecastPoint(
                date=d,
                yhat=max(0.0, yhat),
                yhat_lower=max(0.0, yhat - band),
                yhat_upper=max(0.0, yhat + band),
            )
        )
    return VolumeForecast(
        method="holt_winters",
        history_weeks=len(weekly),
        horizon_weeks=horizon_weeks,
        historical=history_points,
        forecast=fc,
        notes=(
            f"Holt linear (alpha=0.5, beta=0.3). Trend stimato "
            f"{trend:+.1f} mention/settimana, residual std={rstd:.1f}."
        ),
    )


def _std(values: Sequence[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


__all__ = ["forecast_volume"]
