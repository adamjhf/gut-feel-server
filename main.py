import logging
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status  # type: ignore
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.security import OAuth2PasswordBearer  # type: ignore
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

api = APIRouter(prefix="/api", dependencies=[Depends(oauth2_scheme)])


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
        payload = jwt.decode(
            token,
            pub_key,
            algorithms=["RS256"],
            audience=project_id,
            issuer="https://securetoken.google.com/" + project_id,
            require=["iss", "aud", "sub", "exp", "iat", "auth_time"])
        return payload["user_id"]
    except Exception as error:
        print("Error decoding token:", error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@api.put("/stool-log")
async def upsert_stool_log(user_id: Annotated[str,
                                              Depends(get_current_user)],
                           log: model.StoolLogModel,
                           db: model.Session = Depends(get_db)):
    model.upsert_stool_log(db, user_id, log)


@api.put("/food-log")
async def upsert_food_log(user_id: Annotated[str,
                                             Depends(get_current_user)],
                          log: model.FoodLogModel,
                          db: model.Session = Depends(get_db)):
    model.upsert_food_log(db, user_id, log)


@api.put("/symptom-log")
async def upsert_symptom_log(user_id: Annotated[str,
                                                Depends(get_current_user)],
                             log: model.SymptomLogModel,
                             db: model.Session = Depends(get_db)):
    model.upsert_symptom_log(db, user_id, log)


@api.get("/meal-list")
async def get_meal_list(
        response: Response,
        user_id: Annotated[str, Depends(get_current_user)],
        search: str = "",
        db: model.Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "max-age=86400"  # 24 hours
    return model.get_meal_list(db, search, user_id)


@api.put("/logs")
async def upsert_logs(user_id: Annotated[str, Depends(get_current_user)],
                      logs: model.LogEntriesModel,
                      db: model.Session = Depends(get_db)):
    model.upsert_logs(db, user_id, logs)


@api.get("/logs")
async def get_logs(user_id: Annotated[str, Depends(get_current_user)],
                   db: model.Session = Depends(get_db)):
    return model.get_logs(db, user_id)


@api.get("/ingredient-suggestions")
async def get_ingredient_suggestions(
        response: Response,
        user_id: Annotated[str, Depends(get_current_user)],
        search: str = "",
        limit: int = 10,
        db: model.Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "max-age=86400"  # 24 hours
    return model.get_ingredient_suggestions(db, user_id, search, limit)


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


app.include_router(api)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
