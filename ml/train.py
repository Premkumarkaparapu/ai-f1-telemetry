"""
ML Training — AI F1 Telemetry Platform
=======================================
Trains artefacts from all data loaded into the SQLite DB:

  1. laptime_predictor.pkl        — XGBRegressor predicting fuel-corrected lap time
                                    Features: tyre_life, compound, lap_number, stint,
                                              track_enc, session_type_enc, lap_pos_pct
  2. tire_degradation_xgb.pkl    — XGBRegressor for degradation curves (all compounds)
  3. tire_degradation_ridge_<C>  — per-compound Ridge for smooth frontend curves
  4. compound_means.json         — per-compound mean split by track category
  5. feature_meta.json           — saved encodings so inference matches training

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

from backend.app.core.config import MODEL_PATH, DATABASE_URL

COMPOUND_ENCODE = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}
SESSION_ENCODE  = {"R": 0, "Q": 1, "FP1": 2, "FP2": 3, "FP3": 4, "S": 5, "SQ": 6}
MIN_ROWS = 50


# ── Data loading ───────────────────────────────────────────────────────────────

def _load_laps() -> "pd.DataFrame":
    """Load valid laps joined to session (track, session_type) from SQLite."""
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
            l.is_valid,
            d.session_id,
            s.track,
            s.session_type,
            s.event_name,
            s.year
        FROM laps l
        JOIN drivers d ON l.driver_id = d.driver_id
        JOIN sessions s ON d.session_id = s.session_id
        WHERE l.is_valid = 1
          AND l.fuel_corrected_lap_time_ms IS NOT NULL
          AND l.tyre_life IS NOT NULL
          AND l.compound IS NOT NULL
          AND l.compound != 'NAN'
          AND l.fuel_corrected_lap_time_ms BETWEEN 60000 AND 200000
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    engine.dispose()
    logger.info("Loaded %d valid laps from %d sessions", len(df), df["session_id"].nunique())
    return df


# ── Feature engineering ────────────────────────────────────────────────────────

def _build_features(df: "pd.DataFrame", track_enc: dict = None, return_enc: bool = False):
    """Return (X, y) with rich features. Optionally return track_enc dict."""
    import pandas as pd
    import numpy as np

    df = df.copy()

    # Compound encoding
    df["compound_enc"] = df["compound"].str.upper().map(COMPOUND_ENCODE).fillna(1).astype(int)

    # Session type encoding
    df["session_enc"] = df["session_type"].str.upper().map(SESSION_ENCODE).fillna(0).astype(int)

    # Track encoding (ordinal by mean lap time — slower track = higher int)
    if track_enc is None:
        track_means = df.groupby("track")["fuel_corrected_lap_time_ms"].mean().sort_values()
        track_enc   = {t: i for i, t in enumerate(track_means.index)}
    df["track_enc"] = df["track"].map(track_enc).fillna(len(track_enc) // 2).astype(int)

    # Polynomial tyre features
    df["tyre_life_sq"]   = df["tyre_life"] ** 2
    df["tyre_life_root"] = np.sqrt(df["tyre_life"].clip(lower=0))

    # Stint features
    df["stint_number"]  = df["stint_number"].fillna(1).astype(float)
    df["is_first_lap"]  = (df["lap_number"] == 1).astype(int)
    df["is_out_lap"]    = ((df["tyre_life"] <= 2) & (df["lap_number"] > 1)).astype(int)

    features = [
        "tyre_life", "tyre_life_sq", "tyre_life_root",
        "compound_enc", "session_enc", "track_enc",
        "lap_number", "stint_number", "is_first_lap", "is_out_lap",
    ]
    X = df[features]
    y = df["fuel_corrected_lap_time_ms"]

    if return_enc:
        return X, y, track_enc
    return X, y


# ── Model 1: Lap Time Predictor (XGBoost) ─────────────────────────────────────

def train_laptime_predictor(df: "pd.DataFrame", track_enc: dict) -> None:
    import joblib
    import numpy as np
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score
    from xgboost import XGBRegressor

    X, y = _build_features(df, track_enc)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbosity=0,
        n_jobs=-1,
    )
    logger.info("Training laptime_predictor on %d rows …", len(X_tr))
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_te, y_te)],
        verbose=False,
    )

    y_pred = model.predict(X_te)
    rmse = np.sqrt(mean_squared_error(y_te, y_pred))
    r2   = r2_score(y_te, y_pred)
    logger.info("laptime_predictor  RMSE=%.0f ms  R²=%.4f  (test set)", rmse, r2)

    # Feature importances
    fi = dict(zip(X.columns, model.feature_importances_))
    top = sorted(fi.items(), key=lambda x: -x[1])[:5]
    logger.info("Top features: %s", top)

    out = MODEL_PATH / "laptime_predictor.pkl"
    joblib.dump(model, out)
    logger.info("Saved → %s", out)


# ── Model 2: Tire Degradation XGB ─────────────────────────────────────────────

def train_tire_degradation_xgb(df: "pd.DataFrame", track_enc: dict) -> None:
    import joblib
    import numpy as np
    from sklearn.metrics import mean_squared_error
    from xgboost import XGBRegressor

    df2 = df.copy()
    df2["compound_enc"]  = df2["compound"].str.upper().map(COMPOUND_ENCODE).fillna(1)
    df2["tyre_life_sq"]  = df2["tyre_life"] ** 2
    df2["tyre_life_root"]= np.sqrt(df2["tyre_life"].clip(lower=0))
    df2["track_enc"]     = df2["track"].map(track_enc).fillna(len(track_enc)//2)

    X = df2[["tyre_life", "tyre_life_sq", "tyre_life_root", "compound_enc", "track_enc"]]
    y = df2["fuel_corrected_lap_time_ms"]

    model = XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.8,
        random_state=42,
        verbosity=0,
        n_jobs=-1,
    )
    logger.info("Training tire_degradation_xgb on %d rows …", len(X))
    model.fit(X, y)

    rmse = np.sqrt(mean_squared_error(y, model.predict(X)))
    logger.info("tire_degradation_xgb  RMSE=%.0f ms  (train)", rmse)

    joblib.dump(model, MODEL_PATH / "tire_degradation_xgb.pkl")
    logger.info("Saved → tire_degradation_xgb.pkl")


# ── Model 3: Per-Compound Ridge ───────────────────────────────────────────────

def train_per_compound_ridge(df: "pd.DataFrame") -> None:
    import joblib
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    from sklearn.metrics import mean_squared_error

    compounds = df["compound"].str.upper().unique()

    for compound in sorted(compounds):
        sub = df[df["compound"].str.upper() == compound].copy()
        if len(sub) < MIN_ROWS:
            logger.warning("Skipping %s — only %d rows", compound, len(sub))
            continue

        # Use tyre_life + track category for richer curve
        X = sub[["tyre_life"]].values
        y = sub["fuel_corrected_lap_time_ms"].values

        pipe = Pipeline([
            ("poly",   PolynomialFeatures(degree=3, include_bias=False)),
            ("scaler", StandardScaler()),
            ("ridge",  Ridge(alpha=5.0)),
        ])
        pipe.fit(X, y)

        rmse = np.sqrt(mean_squared_error(y, pipe.predict(X)))
        logger.info("ridge[%-12s]  RMSE=%.0f ms  n=%d", compound, rmse, len(sub))

        joblib.dump(pipe, MODEL_PATH / f"tire_degradation_ridge_{compound}.pkl")

    logger.info("All per-compound Ridge models saved.")


# ── Fallback: Compound Means ──────────────────────────────────────────────────

def save_compound_means(df: "pd.DataFrame") -> None:
    """Save mean + std lap time per compound as JSON fallback for inference."""
    import numpy as np
    result = {}
    for c, g in df.groupby(df["compound"].str.upper())["fuel_corrected_lap_time_ms"]:
        result[c] = {
            "mean": round(float(g.mean()), 1),
            "std":  round(float(g.std()),  1),
            "min":  round(float(g.min()),  1),
            "max":  round(float(g.max()),  1),
            "n":    int(len(g)),
        }
    out = MODEL_PATH / "compound_means.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    for c, s in result.items():
        logger.info("  %-14s mean=%.1fs  std=%.1fs  n=%d",
                    c, s["mean"]/1000, s["std"]/1000, s["n"])
    logger.info("Saved compound_means → %s", out)


# ── Save feature metadata ──────────────────────────────────────────────────────

def save_feature_meta(track_enc: dict, df: "pd.DataFrame") -> None:
    """Save track encoding + per-track stats so inference can look them up."""
    track_stats = {}
    for track, grp in df.groupby("track")["fuel_corrected_lap_time_ms"]:
        track_stats[track] = {
            "mean_ms": round(float(grp.mean()), 0),
            "enc":     track_enc.get(track, 0),
        }

    meta = {
        "compound_encode":  COMPOUND_ENCODE,
        "session_encode":   SESSION_ENCODE,
        "track_encode":     track_enc,
        "track_stats":      track_stats,
        "feature_order": [
            "tyre_life", "tyre_life_sq", "tyre_life_root",
            "compound_enc", "session_enc", "track_enc",
            "lap_number", "stint_number", "is_first_lap", "is_out_lap",
        ],
    }
    out = MODEL_PATH / "feature_meta.json"
    with open(out, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Saved feature_meta → %s (%d tracks)", out, len(track_enc))


# ── Master entry point ─────────────────────────────────────────────────────────

def train_all() -> None:
    MODEL_PATH.mkdir(parents=True, exist_ok=True)

    logger.info("Loading laps from DB: %s", DATABASE_URL)
    df = _load_laps()

    if len(df) < MIN_ROWS:
        logger.warning("Only %d valid laps — skipping training. Ingest data first.", len(df))
        out = MODEL_PATH / "compound_means.json"
        with open(out, "w") as f:
            json.dump({"SOFT": {"mean":82000,"std":2000,"min":78000,"max":88000,"n":0}}, f)
        return

    logger.info("=" * 60)
    logger.info("Training on %d laps | %d compounds | %d tracks | %d sessions",
                len(df), df["compound"].nunique(), df["track"].nunique(), df["session_id"].nunique())
    logger.info("=" * 60)

    save_compound_means(df)

    _, _, track_enc = _build_features(df, return_enc=True)
    save_feature_meta(track_enc, df)

    train_laptime_predictor(df, track_enc)
    train_tire_degradation_xgb(df, track_enc)
    train_per_compound_ridge(df)

    logger.info("=" * 60)
    logger.info("✅ All models trained and saved to %s", MODEL_PATH)
    logger.info("=" * 60)


if __name__ == "__main__":
    train_all()
