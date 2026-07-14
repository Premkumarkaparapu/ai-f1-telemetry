"""
ML Training — AI F1 Telemetry Platform
=======================================
Trains three artefacts from data already loaded into the SQLite DB:

  1. laptime_predictor.pkl     — XGBRegressor predicting fuel-corrected lap time
  2. tire_degradation_xgb.pkl  — XGBRegressor for degradation curves (all compounds)
  3. tire_degradation_ridge_<COMPOUND>.pkl — per-compound Ridge for smooth curves
  4. compound_means.json        — fallback mean lap time per compound

Run:
    python -m ml.train
"""

import json
import logging
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
from backend.app.core.config import MODEL_PATH, DATABASE_URL

COMPOUND_ENCODE = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}
MIN_ROWS = 10  # skip training if too little data

# ── Data loading ──────────────────────────────────────────────────────────────

def _load_laps() -> "pd.DataFrame":
    """Load valid laps from SQLite into a DataFrame."""
    import pandas as pd
    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    query = text("""
        SELECT
            l.lap_id,
            l.lap_number,
            l.fuel_corrected_lap_time_ms,
            l.lap_time_ms,
            l.tyre_life,
            l.compound,
            l.stint_number,
            l.is_valid
        FROM laps l
        WHERE l.is_valid = 1
          AND l.fuel_corrected_lap_time_ms IS NOT NULL
          AND l.tyre_life IS NOT NULL
          AND l.compound IS NOT NULL
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    engine.dispose()
    return df


# ── Feature engineering ───────────────────────────────────────────────────────

def _build_features(df: "pd.DataFrame") -> "tuple[pd.DataFrame, pd.Series]":
    """Return (X, y) ready for sklearn/XGBoost."""
    import pandas as pd

    df = df.copy()
    df["compound_enc"] = df["compound"].str.upper().map(COMPOUND_ENCODE).fillna(1)
    df["tyre_life_sq"] = df["tyre_life"] ** 2
    df["is_first_lap"] = (df["lap_number"] == 1).astype(int)
    df["stint_number"] = df["stint_number"].fillna(1)

    features = ["tyre_life", "compound_enc", "tyre_life_sq", "lap_number",
                "is_first_lap", "stint_number"]
    X = df[features]
    y = df["fuel_corrected_lap_time_ms"]
    return X, y


# ── Model 1: Lap Time Predictor ───────────────────────────────────────────────

def train_laptime_predictor(df: "pd.DataFrame") -> None:
    """Train XGBRegressor on all valid laps."""
    import joblib
    import numpy as np
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score

    try:
        from xgboost import XGBRegressor
    except ImportError:
        logger.error("xgboost not installed — run: pip install xgboost")
        return

    X, y = _build_features(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    logger.info("laptime_predictor  RMSE=%.0f ms  R²=%.3f", rmse, r2)

    out = MODEL_PATH / "laptime_predictor.pkl"
    joblib.dump(model, out)
    logger.info("Saved → %s", out)


# ── Model 2: Tire Degradation XGB ────────────────────────────────────────────

def train_tire_degradation_xgb(df: "pd.DataFrame") -> None:
    """Train a single XGBRegressor on (tyre_life, compound_enc, tyre_life_sq) → lap time."""
    import joblib
    import numpy as np
    from sklearn.metrics import mean_squared_error

    try:
        from xgboost import XGBRegressor
    except ImportError:
        logger.error("xgboost not installed")
        return

    df2 = df.copy()
    df2["compound_enc"] = df2["compound"].str.upper().map(COMPOUND_ENCODE).fillna(1)
    df2["tyre_life_sq"] = df2["tyre_life"] ** 2

    X = df2[["tyre_life", "compound_enc", "tyre_life_sq"]]
    y = df2["fuel_corrected_lap_time_ms"]

    model = XGBRegressor(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
        verbosity=0,
    )
    model.fit(X, y)

    y_pred = model.predict(X)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    logger.info("tire_degradation_xgb  RMSE=%.0f ms", rmse)

    out = MODEL_PATH / "tire_degradation_xgb.pkl"
    joblib.dump(model, out)
    logger.info("Saved → %s", out)


# ── Model 3: Per-Compound Ridge ───────────────────────────────────────────────

def train_per_compound_ridge(df: "pd.DataFrame") -> None:
    """Fit a polynomial Ridge per compound for smooth degradation curves."""
    import joblib
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.metrics import mean_squared_error

    compounds = df["compound"].str.upper().unique()

    for compound in compounds:
        sub = df[df["compound"].str.upper() == compound].copy()
        if len(sub) < MIN_ROWS:
            logger.warning("Skipping %s — only %d rows", compound, len(sub))
            continue

        X = sub[["tyre_life"]].values
        y = sub["fuel_corrected_lap_time_ms"].values

        pipe = Pipeline([
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("ridge", Ridge(alpha=10.0)),
        ])
        pipe.fit(X, y)

        y_pred = pipe.predict(X)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        logger.info("ridge[%s]  RMSE=%.0f ms", compound, rmse)

        out = MODEL_PATH / f"tire_degradation_ridge_{compound}.pkl"
        joblib.dump(pipe, out)
        logger.info("Saved → %s", out)


# ── Fallback: Compound Means ──────────────────────────────────────────────────

def save_compound_means(df: "pd.DataFrame") -> None:
    """Save mean lap time per compound as a JSON fallback."""
    means = (
        df.groupby(df["compound"].str.upper())["fuel_corrected_lap_time_ms"]
        .mean()
        .round(1)
        .to_dict()
    )
    out = MODEL_PATH / "compound_means.json"
    with open(out, "w") as f:
        json.dump(means, f, indent=2)
    logger.info("Saved compound means → %s  (%s)", out, means)


# ── Master entry point ────────────────────────────────────────────────────────

def train_all() -> None:
    MODEL_PATH.mkdir(parents=True, exist_ok=True)

    logger.info("Loading laps from DB: %s", DATABASE_URL)
    df = _load_laps()

    if len(df) < MIN_ROWS:
        logger.warning(
            "Only %d valid laps in DB — skipping model training.\n"
            "Run `python -m data_pipeline.load_db` first to ingest data.",
            len(df),
        )
        # Still save an empty compound means so inference.py never crashes
        out = MODEL_PATH / "compound_means.json"
        with open(out, "w") as f:
            json.dump({"SOFT": 82000, "MEDIUM": 85000, "HARD": 88000}, f)
        return

    logger.info("Training on %d laps across %d compounds", len(df), df["compound"].nunique())
    save_compound_means(df)
    train_laptime_predictor(df)
    train_tire_degradation_xgb(df)
    train_per_compound_ridge(df)
    logger.info("✅ All models trained and saved to %s", MODEL_PATH)


if __name__ == "__main__":
    train_all()
