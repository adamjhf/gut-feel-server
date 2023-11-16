import os
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import URL, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

url_object = URL.create(
    "postgresql+psycopg",
    username="postgres",
    password=os.environ['PGPASSWORD'],
    host="freeth.postgres.database.azure.com",
    database="gutfeel_dev",
)

engine = create_engine(url_object)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class StoolLogCreate(BaseModel):
    type: str
    entryTime: datetime
    createdTime: datetime
    lastModifiedTime: datetime
    bristolType: int

    class Config:
        from_attributes = True


class StoolLog(Base):
    __tablename__ = "stool_logs"

    user_id = Column(String, primary_key=True)
    entryTime = Column(DateTime, primary_key=True)
    createdTime = Column(DateTime)
    lastModifiedTime = Column(DateTime)
    bristolType = Column(Integer)


def upsert_stool_log(db: Session, log: StoolLogCreate) -> StoolLog:
    print(log)
    db_log = StoolLog(user_id="test_user",
                      entryTime=log.entryTime,
                      createdTime=log.createdTime,
                      lastModifiedTime=log.lastModifiedTime,
                      bristolType=log.bristolType)
    db.merge(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log
