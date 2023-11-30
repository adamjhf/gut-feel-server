import json
import logging
import os
from typing import Annotated, List

import firebase_admin
import firebase_admin.auth
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi_restful.timing import add_timing_middleware

import model

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

model.Base.metadata.create_all(bind=model.engine)

app = FastAPI()
add_timing_middleware(app, record=logger.debug, exclude="untimed")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

with open("service-account-key-template.json", "r") as f:
    cert = json.load(f)

cert["private_key"] = str(os.getenv("GOOGLE_PRIVATE_KEY")).replace("\\n", "\n")
cred = firebase_admin.credentials.Certificate(cert)
firebase_app = firebase_admin.initialize_app(cred)


def get_db():
    db = model.SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    try:
        payload = firebase_admin.auth.verify_id_token(token,
                                                      check_revoked=True)
        return payload["uid"]
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@app.put("/stool-log")
async def upsert_stool_log(log: model.StoolLogUpsert,
                           db: model.Session = Depends(get_db)):
    model.upsert_stool_log(db, "test_user", log)


@app.put("/food-log")
async def upsert_food_log(log: model.FoodLogUpsert,
                          db: model.Session = Depends(get_db)):
    model.upsert_food_log(db, "test_user", log)


@app.get("/meal-list")
async def get_meal_list(
        user_id: Annotated[str, Depends(get_current_user)],
        search: str = "",
        db: model.Session = Depends(get_db),
):
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
