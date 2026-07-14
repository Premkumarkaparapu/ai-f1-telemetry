"""
Data pipeline — Stage 4: Load
Orchestrates the full Extract → Transform → Feature Engineer → Load pipeline.
Performs idempotency checks before writing to prevent duplicate records.

Usage:
    python -m data_pipeline.load_db

    # Or for a single session:
    python -m data_pipeline.load_db --year 2023 --event "Italian Grand Prix" --type R
"""

import argparse
import fastf1

from backend.app.core.config import TARGET_SESSIONS
from backend.app.core.logging import get_logger, setup_logging
from backend.app.database.db import get_pipeline_db
from backend.app.database.init_db import init_db
from backend.app.database.models import (
    DatasetMetadata,
    Session as SessionModel,
    Driver,
    Lap,
    TelemetryPoint,
    Weather,
    Stint,
    Tyre,
)
from data_pipeline.ingest import ingest_all
from data_pipeline.transform import transform_session, validate_fuel_correction
from data_pipeline.features import engineer_features

setup_logging("pipeline.log")
logger = get_logger(__name__)


def _is_already_loaded(db, year: int, event: str, session_type: str) -> bool:
    """Check DatasetMetadata for an existing import of this session."""
    exists = (
        db.query(DatasetMetadata)
        .filter(
            DatasetMetadata.year == year,
            DatasetMetadata.event_name == event,
            DatasetMetadata.session_type == session_type,
        )
        .first()
    )
    return exists is not None


def load_session(year: int, event: str, session_type: str) -> None:
    """Full pipeline for one session: extract → clean → features → load → metadata."""
    with get_pipeline_db() as db:
        # ── Idempotency check ─────────────────────────────────────────────────
        if _is_already_loaded(db, year, event, session_type):
            logger.info("Session already loaded, skipping: %d %s %s", year, event, session_type)
            return

        logger.info("=== Loading session: %d %s %s ===", year, event, session_type)

        # ── Transform ─────────────────────────────────────────────────────────
        result = transform_session(year, event, session_type)
        session_raw = result["session"]   # FastF1 Session object
        laps_df = result["laps"]
        weather_df = result["weather"]

        # ── Feature engineering ───────────────────────────────────────────────
        laps_df = engineer_features(laps_df)
        validate_fuel_correction(laps_df)

        # ── Insert Session row ────────────────────────────────────────────────
        session_rec = SessionModel(
            year=year,
            event_name=event,
            session_type=session_type,
            track=session_raw.event.get("Location"),
            country=session_raw.event.get("Country"),
            circuit_key=session_raw.event.get("CircuitKey"),
            total_laps=int(laps_df["LapNumber"].max()) if "LapNumber" in laps_df.columns else None,
        )
        db.add(session_rec)
        db.flush()  # populate session_rec.session_id

        # ── Insert Weather ────────────────────────────────────────────────────
        weather_records = [
            Weather(
                session_id=session_rec.session_id,
                time_ms=row.get("time_ms"),
                air_temp=row.get("air_temp"),
                track_temp=row.get("track_temp"),
                humidity=row.get("humidity"),
                pressure=row.get("pressure"),
                wind_speed=row.get("wind_speed"),
                wind_dir=row.get("wind_dir"),
                rainfall=bool(row.get("rainfall", False)),
            )
            for _, row in weather_df.iterrows()
        ]
        db.bulk_save_objects(weather_records)
        logger.info("  Weather: %d rows inserted", len(weather_records))

        # ── Insert Drivers + Laps + Telemetry ─────────────────────────────────
        total_laps_written = 0
        total_tel_written = 0

        driver_codes = laps_df["Driver"].unique(
        ) if "Driver" in laps_df.columns else laps_df["DriverNumber"].unique()

        for code in driver_codes:
            driver_laps = laps_df[laps_df["Driver"] == code] \
                if "Driver" in laps_df.columns \
                else laps_df[laps_df["DriverNumber"] == code]
            if driver_laps.empty:
                continue

            first_row = driver_laps.iloc[0]
            team = first_row.get("Team", None)
            try:
                team_color = "#" + session_raw.get_driver(str(code)).get("TeamColor", "AAAAAA")
            except Exception:
                team_color = "#AAAAAA"

            driver_rec = Driver(
                session_id=session_rec.session_id,
                code=str(code)[:3].upper(),
                full_name=str(first_row.get("Driver", code)),
                team=team,
                team_color=team_color,
            )
            db.add(driver_rec)
            db.flush()

            # Stints for this driver
            if "stint_number" in driver_laps.columns:
                for stint_num, stint_group in driver_laps.groupby("stint_number"):
                    stint_rec = Stint(
                        driver_id=driver_rec.driver_id,
                        session_id=session_rec.session_id,
                        stint_number=int(stint_num),
                        compound=(
                            stint_group["compound"].iloc[0]
                            if "compound" in stint_group.columns else None
                        ),
                        start_lap=int(stint_group["LapNumber"].min()
                                      ) if "LapNumber" in stint_group.columns else None,
                        end_lap=int(stint_group["LapNumber"].max()
                                    ) if "LapNumber" in stint_group.columns else None,
                        tyre_life_start=(
                            int(stint_group["tyre_life"].iloc[0])
                            if "tyre_life" in stint_group.columns else None
                        ),
                    )
                    db.add(stint_rec)

            # Laps
            for _, lap_row in driver_laps.iterrows():
                lap_num = int(lap_row.get("LapNumber", 0)) if "LapNumber" in lap_row.index else 0

                # Snapshot weather at lap start
                if not weather_df.empty and "time_ms" in weather_df.columns:
                    # Find the closest weather reading before this lap
                    pass  # simplified for Week 1 — attach session average

                lap_rec = Lap(
                    driver_id=driver_rec.driver_id,
                    lap_number=lap_num,
                    lap_time_ms=lap_row.get("lap_time_ms"),
                    fuel_corrected_lap_time_ms=lap_row.get("fuel_corrected_lap_time_ms"),
                    sector1_ms=lap_row.get("sector1_ms"),
                    sector2_ms=lap_row.get("sector2_ms"),
                    sector3_ms=lap_row.get("sector3_ms"),
                    compound=lap_row.get("compound"),
                    tyre_life=int(lap_row.get("tyre_life", 0)) if lap_row.get(
                        "tyre_life") else None,
                    stint_number=int(lap_row.get("stint_number", 0)
                                     ) if lap_row.get("stint_number") else None,
                    is_pit_lap=bool(lap_row.get("is_pit_lap", False)),
                    is_valid=bool(lap_row.get("is_valid", True)),
                    track_status=str(lap_row.get("track_status", "1")),
                )
                db.add(lap_rec)
                db.flush()
                total_laps_written += 1

                # Tyre snapshot
                deg_factor = lap_row.get("tyre_degradation_factor")
                if lap_row.get("compound") or lap_row.get("tyre_life"):
                    tyre_rec = Tyre(
                        lap_id=lap_rec.lap_id,
                        compound=lap_row.get("compound"),
                        tyre_life=int(lap_row.get("tyre_life", 0)) if lap_row.get(
                            "tyre_life") else None,
                        degradation_factor=float(deg_factor) if deg_factor and not (
                            deg_factor != deg_factor) else None,
                    )
                    db.add(tyre_rec)

                # Telemetry
                try:
                    tel_df_raw = session_raw.laps.pick_driver(str(code)).pick_lap(lap_num)
                    tel = tel_df_raw.get_telemetry()
                    from data_pipeline.transform import _resample_telemetry
                    tel_resampled = _resample_telemetry(tel)

                    tel_records = []
                    for _, t in tel_resampled.iterrows():
                        tel_records.append(TelemetryPoint(
                            lap_id=lap_rec.lap_id,
                            session_id=session_rec.session_id,
                            time_ms=t.get("time_ms"),
                            distance_m=t.get("distance_m"),
                            speed_kmh=t.get("speed_kmh"),
                            rpm=int(t["RPM"]) if "RPM" in t and t["RPM"] == t["RPM"] else None,
                            gear=int(t.get("gear", 0)) if t.get("gear") == t.get("gear") else None,
                            throttle_pct=t.get("throttle_pct"),
                            brake=bool(t.get("brake", False)),
                            drs=bool(t.get("drs", False)),
                            x=t.get("X"),
                            y=t.get("Y"),
                            z=t.get("Z"),
                            status=str(t.get("Status", ""))[:20] if t.get("Status") else None,
                            source=str(t.get("Source", ""))[:20] if t.get("Source") else None,
                        ))
                    db.bulk_save_objects(tel_records)
                    total_tel_written += len(tel_records)
                except Exception as tel_exc:
                    logger.warning(
                        "Could not load telemetry for %s lap %d: %s", code, lap_num, tel_exc
                    )

            logger.info("  Driver %s: %d laps written", code, len(driver_laps))

        # ── Metadata record ───────────────────────────────────────────────────
        meta = DatasetMetadata(
            year=year,
            event_name=event,
            session_type=session_type,
            fastf1_version=fastf1.__version__,
            pipeline_version="1.0.0",
            row_count_laps=total_laps_written,
            row_count_telemetry=total_tel_written,
        )
        db.add(meta)

        logger.info(
            "=== Session loaded: %d laps, %d telemetry rows ===",
            total_laps_written,
            total_tel_written,
        )


def main(sessions=None):
    """Run the full ETL pipeline for all (or specified) sessions."""
    init_db()
    targets = sessions or TARGET_SESSIONS
    logger.info("Starting ingest from FastF1...")
    ingest_all(targets)  # ingest exactly the sessions we need

    for year, event, session_type in targets:
        load_session(year, event, session_type)

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI F1 Telemetry Pipeline")
    parser.add_argument("--year", type=int, help="Session year")
    parser.add_argument("--event", type=str, help="Event name (e.g. 'Italian Grand Prix')")
    parser.add_argument("--type", dest="session_type", type=str, help="Session type (R, Q, FP1...)")
    args = parser.parse_args()

    if args.year and args.event and args.session_type:
        sessions = [(args.year, args.event, args.session_type)]
    else:
        sessions = None

    main(sessions)
