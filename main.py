import logging
from typing import List

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_restful.timing import add_timing_middleware

import model

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

model.Base.metadata.create_all(bind=model.engine)

app = FastAPI()
add_timing_middleware(app, record=logger.debug, exclude="untimed")


def get_db():
    db = model.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.put("/stool-log")
async def upsert_stool_log(log: model.StoolLogUpsert,
                           db: model.Session = Depends(get_db)):
    model.upsert_stool_log(db, "test_user", log)


@app.put("/food-log")
async def upsert_food_log(log: model.FoodLogUpsert,
                          db: model.Session = Depends(get_db)):
    model.upsert_food_log(db, "test_user", log)


@app.get("/meal-list")
async def get_meal_list(search: str = "", db: model.Session = Depends(get_db)):
    user_id = "test_user"
    return model.get_meal_list(db, search, user_id)


@app.put("/sync-local-logs")
async def upsert_logs(logs: List[model.FoodLogUpsert | model.StoolLogUpsert],
                      db: model.Session = Depends(get_db)):
    model.upsert_logs(db, "test_user", logs)


@app.get("/")
async def root():
    return {"Hello": "World!"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request,
                                       exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    logging.error(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content,
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
