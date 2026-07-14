"""Prediction repository — isolates all prediction-related SQL queries."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.database.models import Prediction


class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, prediction: Prediction) -> Prediction:
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    def get_by_session_driver(self, session_id: int, driver_id: int) -> list[Prediction]:
        return (
            self.db.query(Prediction)
            .filter(
                Prediction.session_id == session_id,
                Prediction.driver_id == driver_id,
            )
            .order_by(Prediction.created_at.desc())
            .all()
        )

    def get_by_id(self, prediction_id: int) -> Optional[Prediction]:
        return (
            self.db.query(Prediction)
            .filter(Prediction.prediction_id == prediction_id)
            .first()
        )

    def get_by_session(self, session_id: int) -> list[Prediction]:
        return (
            self.db.query(Prediction)
            .filter(Prediction.session_id == session_id)
            .order_by(Prediction.created_at.desc())
            .all()
        )

