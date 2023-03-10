import os
from sqlalchemy import String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DB_URL = os.environ.get("DB_URL")
engine = create_async_engine(DB_URL)


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = 'patients'

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    forename: Mapped[str]
    surname: Mapped[str]
