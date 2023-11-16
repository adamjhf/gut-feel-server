import logging
from typing import Union

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import model

model.Base.metadata.create_all(bind=model.engine)

app = FastAPI()


def get_db():
    db = model.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.put("/stool-log")
async def upsert_stool_log(log: model.StoolLogCreate,
                           db: model.Session = Depends(get_db)):
    return model.upsert_stool_log(db, log)


@app.get("/")
def read_root():
    return {"Hello": "World!"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request,
                                       exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    logging.error(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content,
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
