import json
import os
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    URL,  # type: ignore
    Uuid,  # type: ignore
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
    desc,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

url_object = URL.create(
    "postgresql+psycopg",
    username=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ["PGHOST"],
    database=os.environ["PGDATABASE"],
    port=os.environ["PGPORT"],
)

engine = create_engine(url_object)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class LogModel(BaseModel):
    id: UUID
    entryTime: datetime
    createdTime: datetime
    lastModifiedTime: datetime
    deleted: bool

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        }


class StoolLogModel(LogModel):
    bristolType: int
    tags: list[str]


class FoodLogModel(LogModel):
    meal: str
    ingredients: list[str]


class SymptomLogModel(LogModel):
    symptoms: dict[str, int]


class LogEntriesModel(BaseModel):
    stool: list[StoolLogModel]
    food: list[FoodLogModel]
    symptom: list[SymptomLogModel]

    class Config:
        from_attributes = True


class MealSearchResult(BaseModel):
    meal: str
    ingredients: list[str]


class StoolLog(Base):
    __tablename__ = "stool_logs"
    id = Column(Uuid, primary_key=True, default=func.uuid_generate_v4())
    user_id = Column(String)
    entry_time = Column(DateTime)
    created_time = Column(DateTime)
    last_modified_time = Column(DateTime)
    bristol_type = Column(Integer)
    tags = Column(String)
    deleted = Column(Boolean)


class FoodLog(Base):
    __tablename__ = "food_logs"

    id = Column(Uuid, primary_key=True, default=func.uuid_generate_v4())
    user_id = Column(String)
    entry_time = Column(DateTime)
    created_time = Column(DateTime)
    last_modified_time = Column(DateTime)
    meal = Column(String)
    ingredients = Column(String)
    deleted = Column(Boolean)


class SymptomLog(Base):
    __tablename__ = "symptom_logs"

    id = Column(Uuid, primary_key=True, default=func.uuid_generate_v4())
    user_id = Column(String)
    entry_time = Column(DateTime)
    created_time = Column(DateTime)
    last_modified_time = Column(DateTime)
    symptoms = Column(String)
    deleted = Column(Boolean)


def upsert_stool_log(db: Session,
                     user_id: str,
                     log: StoolLogModel,
                     commit: bool = True) -> None:
    db_log = StoolLog(
        id=log.id,
        user_id=user_id,
        entry_time=log.entryTime,
        created_time=log.createdTime,
        last_modified_time=log.lastModifiedTime,
        bristol_type=log.bristolType,
        tags=json.dumps(log.tags),
        deleted=log.deleted,
    )
    db.merge(db_log)
    if commit:
        db.commit()


def upsert_food_log(db: Session,
                    user_id: str,
                    log: FoodLogModel,
                    commit: bool = True) -> None:
    if log.meal == "" or len(log.ingredients) == 0:
        raise Exception("meal or ingredients cannot be empty")
    db_log = FoodLog(
        id=log.id,
        user_id=user_id,
        entry_time=log.entryTime,
        created_time=log.createdTime,
        last_modified_time=log.lastModifiedTime,
        meal=log.meal,
        ingredients=json.dumps(log.ingredients),
        deleted=log.deleted,
    )
    db.merge(db_log)
    if commit:
        db.commit()


def upsert_symptom_log(db: Session,
                       user_id: str,
                       log: SymptomLogModel,
                       commit: bool = True) -> None:
    if len(log.symptoms) == 0:
        raise Exception("symptoms list cannot be empty")
    db_log = SymptomLog(
        id=log.id,
        user_id=user_id,
        entry_time=log.entryTime,
        created_time=log.createdTime,
        last_modified_time=log.lastModifiedTime,
        symptoms=json.dumps(log.symptoms),
        deleted=log.deleted,
    )
    db.merge(db_log)
    if commit:
        db.commit()


def get_meal_list(db: Session, search: str,
                  user_id: str) -> list[MealSearchResult]:
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


def upsert_logs(db: Session, user_id: str, logs: LogEntriesModel) -> None:
    for log in logs.stool:
        upsert_stool_log(db, user_id, log, False)
    for log in logs.food:
        upsert_food_log(db, user_id, log, False)
    for log in logs.symptom:
        upsert_symptom_log(db, user_id, log, False)
    db.commit()


def get_logs(
    db: Session,
    user_id: str,
    since: datetime = datetime.min
) -> dict[str, list[StoolLogModel] | list[FoodLogModel]
          | list[SymptomLogModel]]:
    stool_logs = db.query(StoolLog).filter(
        StoolLog.user_id == user_id,
        StoolLog.last_modified_time >= since).all()
    food_logs = db.query(FoodLog).filter(
        FoodLog.user_id == user_id, FoodLog.last_modified_time >= since).all()
    symptom_logs = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id,
        SymptomLog.last_modified_time >= since).all()
    return {
        "stool": [
            StoolLogModel(id=s.id,
                          entryTime=s.entry_time,
                          createdTime=s.created_time,
                          lastModifiedTime=s.last_modified_time,
                          bristolType=s.bristol_type,
                          tags=json.loads(s.tags),
                          deleted=s.deleted) for s in stool_logs
        ],
        "food": [
            FoodLogModel(id=f.id,
                         entryTime=f.entry_time,
                         createdTime=f.created_time,
                         lastModifiedTime=f.last_modified_time,
                         meal=f.meal,
                         ingredients=json.loads(f.ingredients),
                         deleted=f.deleted) for f in food_logs
        ],
        "symptom": [
            SymptomLogModel(id=s.id,
                            entryTime=s.entry_time,
                            createdTime=s.created_time,
                            lastModifiedTime=s.last_modified_time,
                            symptoms=json.loads(s.symptoms),
                            deleted=s.deleted) for s in symptom_logs
        ]
    }


def get_ingredient_suggestions(db: Session,
                               user_id: str,
                               search: str = "",
                               limit: int = 10):
    subq = db.query(func.json_array_elements_text(FoodLog.ingredients.cast(JSON)) \
                 .label("ingredient")) \
        .filter(FoodLog.user_id == user_id) \
        .subquery()
    q = db.query(subq) \
        .filter(subq.c.ingredient.ilike(f"%{search}%")) \
        .group_by(subq.c.ingredient) \
        .order_by(desc(func.count(subq.c.ingredient))) \
        .limit(limit)
    return [i.ingredient for i in q.all()]
