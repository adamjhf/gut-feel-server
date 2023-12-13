FROM python:3.10

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

RUN pip install -r requirements.txt

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1