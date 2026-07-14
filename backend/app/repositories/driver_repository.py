"""Driver repository — isolates all driver-related SQL queries."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.database.models import Driver


class DriverRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_session(self, session_id: int) -> list[Driver]:
        return (
            self.db.query(Driver)
            .filter(Driver.session_id == session_id)
            .order_by(Driver.code)
            .all()
        )

    def get_by_code(self, session_id: int, code: str) -> Optional[Driver]:
        return (
            self.db.query(Driver)
            .filter(Driver.session_id == session_id, Driver.code == code.upper())
            .first()
        )

    def get_by_id(self, driver_id: int) -> Optional[Driver]:
        return self.db.query(Driver).filter(Driver.driver_id == driver_id).first()
