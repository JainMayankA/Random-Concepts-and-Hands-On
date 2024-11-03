FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN touch crdt/__init__.py server/__init__.py tests/__init__.py

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
