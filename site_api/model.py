import os
from datetime import datetime, date

from sqlalchemy import (
    String,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)


DB_URL = os.environ.get("DB_URL")
engine = create_async_engine(DB_URL)


class Patient(Base):
    __tablename__ = 'patients'

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    forename: Mapped[str]
    surname: Mapped[str]
    birth_date: Mapped[date]

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    modified_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=True
    )
