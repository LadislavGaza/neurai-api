import os
from sqlalchemy import (
    Column,
    Integer,
    String
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine


engine = create_async_engine(os.environ.get('DB_URL'), future=True)
Base = declarative_base()


class Example(Base):
    __tablename__ = 'example'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
