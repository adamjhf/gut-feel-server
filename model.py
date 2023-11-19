import json
import os
from datetime import datetime
from typing import List

from pydantic import BaseModel
from sqlalchemy import URL, Column, DateTime, Integer, String, create_engine, func
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


class FoodLogCreate(BaseModel):
    type: str
    entryTime: datetime
    createdTime: datetime
    lastModifiedTime: datetime
    meal: str
    ingredients: List[str]

    class Config:
        from_attributes = True


class MealSearchResult(BaseModel):
    meal: str
    ingredients: List[str]


class StoolLog(Base):
    __tablename__ = "stool_logs"

    user_id = Column(String, primary_key=True)
    entry_time = Column(DateTime)
    created_time = Column(DateTime, primary_key=True)
    last_modified_time = Column(DateTime)
    bristol_type = Column(Integer)


class FoodLog(Base):
    __tablename__ = "food_logs"

    user_id = Column(String, primary_key=True)
    entry_time = Column(DateTime)
    created_time = Column(DateTime, primary_key=True)
    last_modified_time = Column(DateTime)
    meal = Column(String)
    ingredients = Column(String)


def upsert_stool_log(db: Session,
                     user_id: str,
                     log: StoolLogCreate,
                     commit: bool = True) -> None:
    db_log = StoolLog(
        user_id=user_id,
        entry_time=log.entryTime,
        created_time=log.createdTime,
        last_modified_time=log.lastModifiedTime,
        bristol_type=log.bristolType,
    )
    db.merge(db_log)
    if commit:
        db.commit()


def upsert_food_log(db: Session,
                    user_id: str,
                    log: FoodLogCreate,
                    commit: bool = True) -> None:
    db_log = FoodLog(
        user_id=user_id,
        entry_time=log.entryTime,
        created_time=log.createdTime,
        last_modified_time=log.lastModifiedTime,
        meal=log.meal,
        ingredients=json.dumps(log.ingredients),
    )
    db.merge(db_log)
    if commit:
        db.commit()


def get_meal_list(db: Session, search: str,
                  user_id: str) -> List[MealSearchResult]:
    row_num = func.row_number() \
        .over(partition_by=FoodLog.meal,
              order_by=FoodLog.entry_time.desc()) \
        .label("row_num")
    subq = db.query(FoodLog.meal, FoodLog.ingredients, row_num,
                   func.count().over(partition_by=FoodLog.meal).label("cnt")) \
        .filter(FoodLog.user_id == user_id) \
        .filter(FoodLog.meal.ilike(f"%{search}%")) \
        .subquery()
    q = db.query(subq).filter(subq.c.row_num == 1).order_by(subq.c.cnt.desc())

    return [
        MealSearchResult(meal=meal.meal,
                         ingredients=json.loads(meal.ingredients))
        for meal in q.all()
    ]


def upsert_logs(db: Session, user_id: str,
                logs: List[FoodLogCreate | StoolLogCreate]) -> None:
    for log in logs:
        if isinstance(log, StoolLogCreate):
            upsert_stool_log(db, user_id, log, False)
        elif isinstance(log, FoodLogCreate):
            upsert_food_log(db, user_id, log, False)
        else:
            raise Exception("Invalid log type")
    db.commit()
