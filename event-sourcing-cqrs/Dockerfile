FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN touch domain/__init__.py domain/events/__init__.py domain/aggregates/__init__.py \
    store/__init__.py projections/__init__.py sagas/__init__.py api/__init__.py tests/__init__.py

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
