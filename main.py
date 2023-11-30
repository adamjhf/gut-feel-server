import logging
import os
from typing import Annotated, List

import jwt
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
jwks_url = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
project_id = str(os.getenv("PROJECT_ID"))
jwk_client = jwt.PyJWKClient(jwks_url)


def get_db():
    db = model.SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    try:
        pub_key = jwk_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(token,
                             pub_key,
                             algorithms=["RS256"],
                             audience=project_id,
                             iss="https://securetoken.google.com/" +
                             project_id,
                             require=["iss", "aud", "sub", "exp", "iat"])
        return payload["user_id"]
    except Exception as error:
        print("Error decoding token:", error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@app.put("/stool-log")
async def upsert_stool_log(user_id: Annotated[str,
                                              Depends(get_current_user)],
                           log: model.StoolLogUpsert,
                           db: model.Session = Depends(get_db)):
    model.upsert_stool_log(db, user_id, log)


@app.put("/food-log")
async def upsert_food_log(user_id: Annotated[str,
                                             Depends(get_current_user)],
                          log: model.FoodLogUpsert,
                          db: model.Session = Depends(get_db)):
    model.upsert_food_log(db, user_id, log)


@app.get("/meal-list")
async def get_meal_list(
        user_id: Annotated[str, Depends(get_current_user)],
        search: str = "",
        db: model.Session = Depends(get_db),
):
    return model.get_meal_list(db, search, user_id)


@app.put("/sync-local-logs")
async def upsert_logs(user_id: Annotated[str, Depends(get_current_user)],
                      logs: List[model.FoodLogUpsert | model.StoolLogUpsert],
                      db: model.Session = Depends(get_db)):
    model.upsert_logs(db, user_id, logs)


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
