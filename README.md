# AI F1 Telemetry Platform

A production-grade, ML-driven Formula 1 race strategy and telemetry analysis platform. Built to demonstrate full-stack engineering, time-series data pipelines, and applied machine learning on real F1 data.

## 🚀 Live Deployment

| Service | URL | Status |
|---|---|---|
| 🌐 **Frontend (Vercel)** | https://f1-telemetry-fctsoznr2-premkumarkaparapus-projects.vercel.app | [![Vercel](https://img.shields.io/badge/Vercel-Live-brightgreen)](https://f1-telemetry-fctsoznr2-premkumarkaparapus-projects.vercel.app) |
| ⚙️ **Backend API (Render)** | https://f1-telemetry-api.onrender.com | [![Render](https://img.shields.io/badge/Render-Live-brightgreen)](https://f1-telemetry-api.onrender.com/health) |
| 📖 **API Docs** | https://f1-telemetry-api.onrender.com/docs | Swagger UI |

> ⚠️ **Note:** The backend runs on Render's free tier — it may take 30–60 seconds to wake up after inactivity.

---


## Architecture

```
┌──────────────────┐   ┌──────────────────┐   ┌───────────────────┐
│   React Frontend │──▶│  FastAPI Backend  │──▶│   SQLite / PG DB  │
│   (Vite + Chart) │   │  /api/v1/*        │   │   10 tables       │
└──────────────────┘   └────────┬─────────┘   └───────────────────┘
                                │
                        ┌───────▼──────────┐
                        │  ML Layer        │
                        │  XGBoost + Ridge │
                        │  joblib models   │
                        └──────────────────┘
                                │
                        ┌───────▼──────────┐
                        │  Data Pipeline   │
                        │  FastF1 → 5Hz    │
                        │  Parquet cache   │
                        └──────────────────┘
```

## Quickstart

### 1. Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

### 2. Initialise the database

```bash
python -m backend.app.database.init_db
```

### 3. Ingest real F1 data (FastF1)

```bash
# Example: 2024 Bahrain GP qualifying
python -m data_pipeline.load_db --year 2024 --event "Bahrain Grand Prix" --session Q

# Or load a full race weekend
python -m data_pipeline.load_db --year 2024 --event "Monaco Grand Prix" --session R
```

### 4. Train ML models

```bash
python -m ml.train
```

Models saved to `ml/models/`:
- `laptime_predictor.pkl` — XGBoost lap time predictor
- `tire_degradation_xgb.pkl` — Global degradation model
- `tire_degradation_ridge_SOFT.pkl` etc. — Per-compound Ridge
- `compound_means.json` — Mean lap time fallback

### 5. Start the API server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 6. Start the frontend

```bash
cd frontend
npm run dev
```

Dashboard: http://localhost:5173

---

## API Endpoints

### Sessions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/sessions/` | List all sessions |
| GET | `/api/v1/sessions/{id}` | Session detail |
| GET | `/api/v1/sessions/{id}/weather` | Weather telemetry |
| GET | `/api/v1/sessions/{id}/standings` | Driver standings |

### Drivers & Laps
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/drivers/?session_id=` | Drivers in session |
| GET | `/api/v1/laps/?driver_id=` | All laps for driver |
| GET | `/api/v1/laps/stints/` | Stint summary |
| GET | `/api/v1/laps/pitstops/` | Pit stop data |

### Telemetry
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/telemetry/{lap_id}` | Full 5Hz telemetry trace |
| GET | `/api/v1/telemetry/{lap_id}/summary` | Peak/mean stats |
| GET | `/api/v1/telemetry/compare/laps` | Two-lap overlay data |

### Predictions & Strategy
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/predict/` | Lap time prediction |
| POST | `/api/v1/predict/strategy` | Race strategy simulation |
| GET | `/api/v1/predict/degradation/{compound}` | Degradation curve |
| GET | `/api/v1/predict/pit-window/{session}/{driver}` | Pit window advisor |
| GET | `/api/v1/predict/history/{session_id}` | Prediction log |

---

## Frontend Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Session KPIs, driver standings table |
| **Lap Compare** | Overlay telemetry traces for two drivers |
| **Degradation** | ML-predicted tyre degradation curves |
| **Strategy Sim** | Simulate pit strategies, see per-lap time chart + pit window |
| **Live Replay** | Animated telemetry scrubber with speed trace + track map |

---

## ML Models

### Tire Degradation
- **XGBRegressor** trained on `(tyre_life, compound_enc, tyre_life²)` → `fuel_corrected_lap_time_ms`
- **Per-compound Ridge** with `PolynomialFeatures(degree=2)` for smooth curves
- Fallback chain: Ridge → XGB → linear extrapolation from compound mean

### Lap Time Predictor
- **XGBRegressor** with features: `tyre_life, compound_enc, tyre_life², lap_number, is_first_lap, stint_number`
- 80/20 train/test split, logs RMSE + R²

### Strategy Simulation
- Hybrid: real lap times from DB where available, ML predictions for future laps
- Pit lane time loss configurable (default 25 s)
- Returns `vs_baseline_ms` — delta vs no-strategy-change

### Pit Window Advisor
- Evaluates every candidate pit lap in `[current+2, total-6]`
- Minimises: `stay_out_cost + fresh_tyre_cost + pit_lane_loss`
- Falls back to rule-of-thumb heuristics if models unavailable

---

## Project Structure

```
ai-f1-telemetry/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI routers
│   │   ├── core/            # Config, logging, constants
│   │   ├── database/        # SQLAlchemy models, init
│   │   ├── repositories/    # DB query layer
│   │   ├── services/        # Business logic
│   │   └── schemas/         # Pydantic request/response models
│   └── requirements.txt
├── data_pipeline/
│   ├── ingest.py            # FastF1 → raw Parquet
│   ├── transform.py         # 5Hz resample, fuel correction
│   ├── features.py          # Degradation slope, deltas
│   └── load_db.py           # Parquet → SQLite
├── ml/
│   ├── train.py             # Train all models
│   ├── inference.py         # Inference functions
│   └── models/              # Saved .pkl + .json artefacts
├── frontend/
│   ├── src/
│   │   ├── pages/           # Dashboard, LapComparison, Degradation, Strategy, LiveReplay
│   │   ├── App.jsx          # Sidebar navigation shell
│   │   ├── api.js           # API client
│   │   ├── utils.jsx        # Formatting + CompoundBadge
│   │   └── index.css        # Dark theme design system
│   └── package.json
└── tests/                   # 29 unit tests (pytest)
```

---

## Engineering Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite default, Postgres via env | Zero-config for dev, production-ready via `DATABASE_URL` |
| 5Hz telemetry downsample | Prevents 500MB+ DB on race weekends while preserving corner fidelity |
| Parquet intermediate cache | Schema changes don't require re-downloading from FastF1 |
| Joblib lazy imports in inference | `import inference` never crashes if XGBoost not installed |
| Repository layer | Decouples SQL from business logic; testable with in-memory SQLite |
| `/api/v1/` prefix | Future-proof; `/api/v2/` can coexist without breaking clients |

---

## Tests

```bash
python -m pytest tests/ -v
# 29 passed
```

All tests use in-memory SQLite with `StaticPool` — no external services required.
