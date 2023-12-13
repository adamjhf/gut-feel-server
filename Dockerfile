FROM python:3.10

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD exec uvicorn --port $PORT --host 0.0.0.0 main:app