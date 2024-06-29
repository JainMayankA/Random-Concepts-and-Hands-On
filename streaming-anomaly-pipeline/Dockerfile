FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN touch pipeline/__init__.py detector/__init__.py api/__init__.py tests/__init__.py

CMD ["python", "-m", "pipeline.main"]
