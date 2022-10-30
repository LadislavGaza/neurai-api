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


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
