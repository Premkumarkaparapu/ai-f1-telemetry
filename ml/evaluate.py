"""Academic ML Evaluation Script — AI F1 Telemetry Platform.

Splits data chronologically (2023 Train, 2024 Validation, 2025-26 Test).
Performs leakage-proof preprocessing (fitting only on 2023 Train data).
Saves preprocessing mappings, evaluation stats, and baseline comparisons.
"""

import json
import logging
from datetime import datetime
import numpy as np
import pandas as pd
import joblib

from backend.app.core.config import DATABASE_URL, MODEL_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

COMPOUND_ENCODE = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}
SESSION_ENCODE = {"R": 0, "Q": 1, "FP1": 2, "FP2": 3, "FP3": 4, "S": 5, "SQ": 6}


def load_data() -> pd.DataFrame:
    """Load valid laps joined to sessions from the database."""
    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL)
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
    logger.info("Loaded %d total laps for chronological evaluation.", len(df))
    return df


def preprocess_split(df: pd.DataFrame, track_enc: dict) -> pd.DataFrame:
    """Transform features using pre-fitted encoders to prevent data leakage."""
    df = df.copy()

    # Compound encoding
    df["compound_enc"] = (
        df["compound"].str.upper().map(COMPOUND_ENCODE).fillna(1).astype(int)
    )

    # Session type encoding
    df["session_enc"] = (
        df["session_type"].str.upper().map(SESSION_ENCODE).fillna(0).astype(int)
    )

    # Track encoding using pre-fitted track_enc mapping
    fallback_val = len(track_enc) // 2 if track_enc else 0
    df["track_enc"] = (
        df["track"].map(track_enc).fillna(fallback_val).astype(int)
    )

    # Polynomial tyre features
    df["tyre_life_sq"] = df["tyre_life"] ** 2
    df["tyre_life_root"] = np.sqrt(df["tyre_life"].clip(lower=0))

    # Stint features
    df["stint_number"] = df["stint_number"].fillna(1).astype(float)
    df["is_first_lap"] = (df["lap_number"] == 1).astype(int)
    df["is_out_lap"] = ((df["tyre_life"] <= 2) & (df["lap_number"] > 1)).astype(int)

    return df


def evaluate_model(y_true, y_pred):
    """Compute MAE, RMSE, and R2 metrics."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "r2": round(r2, 4)}


def run_evaluation() -> None:
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    df = load_data()

    if len(df) < 50:
        logger.warning("Not enough laps in DB for evaluation.")
        return

    # Chronological Splits
    df_train = df[df["year"] == 2023].copy()
    df_val = df[df["year"] == 2024].copy()
    df_test = df[df["year"].isin([2025, 2026])].copy()

    # Fallback if 2024 is empty (since there is no 2024 data in this database)
    if len(df_val) == 0 and len(df_train) > 10:
        logger.info(
            "Validation set (2024) is empty. Performing chronological "
            "80/20 split on 2023 data for Train/Validation..."
        )
        df_2023 = df_train.sort_values("session_id")
        split_idx = int(len(df_2023) * 0.8)
        df_train = df_2023.iloc[:split_idx].copy()
        df_val = df_2023.iloc[split_idx:].copy()

    logger.info(
        "Splits size -> Train (2023-part1): %d, Validation (2023-part2): %d, "
        "Test (2025-26): %d",
        len(df_train), len(df_val), len(df_test)
    )

    # 1. Fit Track Encoding strictly on 2023 Train data
    track_means_2023 = (
        df_train.groupby("track")["fuel_corrected_lap_time_ms"]
        .mean()
        .sort_values()
    )
    track_enc_2023 = {t: i for i, t in enumerate(track_means_2023.index)}

    # 2. Fit Baseline (Mean compound fallback) strictly on 2023 Train data
    compound_means_2023 = {}
    global_mean_2023 = float(df_train["fuel_corrected_lap_time_ms"].mean())
    groupby_comp = df_train.groupby(df_train["compound"].str.upper())
    for comp, grp in groupby_comp["fuel_corrected_lap_time_ms"]:
        compound_means_2023[comp] = float(grp.mean())

    # 3. Preprocess all splits using 2023-fitted track encoding
    df_train_proc = preprocess_split(df_train, track_enc_2023)
    df_val_proc = preprocess_split(df_val, track_enc_2023)
    df_test_proc = preprocess_split(df_test, track_enc_2023)

    features = [
        "tyre_life", "tyre_life_sq", "tyre_life_root",
        "compound_enc", "session_enc", "track_enc",
        "lap_number", "stint_number", "is_first_lap", "is_out_lap",
    ]

    X_train, y_train = df_train_proc[features], df_train_proc["fuel_corrected_lap_time_ms"]
    X_val, y_val = df_val_proc[features], df_val_proc["fuel_corrected_lap_time_ms"]
    X_test, y_test = df_test_proc[features], df_test_proc["fuel_corrected_lap_time_ms"]

    # 4. Serialize preprocessing pipeline mapping
    pipeline_data = {
        "track_encode": track_enc_2023,
        "compound_encode": COMPOUND_ENCODE,
        "session_encode": SESSION_ENCODE,
        "features": features
    }
    pipeline_out = MODEL_PATH / "preprocessing_pipeline.pkl"
    joblib.dump(pipeline_data, pipeline_out)
    logger.info("Saved fitted preprocessing pipeline -> %s", pipeline_out)

    # ── Train Models ──

    # A. Train Ridge Regressor on 2023
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    from sklearn.linear_model import Ridge
    pipe_ridge = Pipeline([
        ("poly", PolynomialFeatures(degree=3, include_bias=False)),
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=5.0)),
    ])
    pipe_ridge.fit(X_train[["tyre_life"]], y_train)

    # B. Train XGBoost Regressor on 2023
    from xgboost import XGBRegressor
    model_xgb = XGBRegressor(
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
    model_xgb.fit(X_train, y_train)

    # Serialize locked laptime predictor XGBoost model
    xgb_out = MODEL_PATH / "laptime_predictor.pkl"
    joblib.dump(model_xgb, xgb_out)
    logger.info("Saved trained laptime predictor model -> %s", xgb_out)

    # ── Predict & Evaluate ──

    # Baseline Predictions Helper
    def get_baseline_preds(df_proc):
        mapped = df_proc["compound"].str.upper().map(compound_means_2023)
        return mapped.fillna(global_mean_2023).values

    # 1. Train Evaluation
    metrics_train = {
        "baseline": evaluate_model(y_train, get_baseline_preds(df_train_proc)),
        "ridge": evaluate_model(y_train, pipe_ridge.predict(X_train[["tyre_life"]])),
        "xgboost": evaluate_model(y_train, model_xgb.predict(X_train))
    }

    # 2. Validation Evaluation
    metrics_val = {
        "baseline": evaluate_model(y_val, get_baseline_preds(df_val_proc)),
        "ridge": evaluate_model(y_val, pipe_ridge.predict(X_val[["tyre_life"]])),
        "xgboost": evaluate_model(y_val, model_xgb.predict(X_val))
    }

    # 3. Test Evaluation
    metrics_test = {
        "baseline": evaluate_model(y_test, get_baseline_preds(df_test_proc)),
        "ridge": evaluate_model(y_test, pipe_ridge.predict(X_test[["tyre_life"]])),
        "xgboost": evaluate_model(y_test, model_xgb.predict(X_test))
    }

    # Compute compound-level and track-level MAE/RMSE for final test set (XGBoost)
    test_predictions = model_xgb.predict(X_test)
    df_test_eval = df_test_proc.copy()
    df_test_eval["pred"] = test_predictions
    diff_eval = (
        df_test_proc["fuel_corrected_lap_time_ms"] - df_test_eval["pred"]
    )
    df_test_eval["abs_err"] = np.abs(diff_eval)
    df_test_eval["sq_err"] = diff_eval ** 2

    # Group by compound
    compound_test_metrics = {}
    for comp, grp in df_test_eval.groupby("compound"):
        mae = float(grp["abs_err"].mean())
        rmse = float(np.sqrt(grp["sq_err"].mean()))
        compound_test_metrics[comp.upper()] = {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "n": len(grp)
        }

    # Group by track
    track_test_metrics = {}
    for trk, grp in df_test_eval.groupby("track"):
        mae = float(grp["abs_err"].mean())
        rmse = float(np.sqrt(grp["sq_err"].mean()))
        track_test_metrics[trk] = {"mae": round(mae, 2), "rmse": round(rmse, 2), "n": len(grp)}

    # Save JSON report
    report = {
        "dataset_boundaries": {
            "train": 2023,
            "validation": 2024,
            "test": "2025-2026"
        },
        "number_of_samples": {
            "train": len(df_train),
            "validation": len(df_val),
            "test": len(df_test)
        },
        "features_used": features,
        "train": metrics_train,
        "validation": metrics_val,
        "final_test": metrics_test,
        "compound_level_test_metrics": compound_test_metrics,
        "track_level_test_metrics": track_test_metrics,
        "model_version": "2.7.0",
        "evaluation_timestamp": datetime.utcnow().isoformat()
    }

    report_out = MODEL_PATH / "evaluation_report.json"
    with open(report_out, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Saved evaluation report -> %s", report_out)

    # Print validation summary
    print("\n" + "=" * 80)
    print("F1 TELEMETRY MODEL COMPARISON SUMMARY (CHRONOLOGICAL SPLITS)")
    print("=" * 80)
    headers = (
        f"{'Split':<12} | {'Model':<10} | {'MAE (ms)':<10} | "
        f"{'RMSE (ms)':<10} | {'R² Score':<10}"
    )
    print(headers)
    print("-" * 80)

    splits_list = [
        ("Train 2023", metrics_train),
        ("Val 2024", metrics_val),
        ("Test 2025-26", metrics_test),
    ]
    for split_name, metrics in splits_list:
        for model_name in ["baseline", "ridge", "xgboost"]:
            m = metrics[model_name]
            print(
                f"{split_name:<12} | {model_name:<10} | "
                f"{m['mae']:<10.2f} | {m['rmse']:<10.2f} | "
                f"{m['r2']:<10.4f}"
            )
        print("-" * 80)
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_evaluation()
