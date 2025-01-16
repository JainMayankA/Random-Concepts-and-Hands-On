FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN touch model/__init__.py pipeline/__init__.py api/__init__.py tests/__init__.py

ENV MODEL_CHECKPOINT=""
ENV DEVICE="cpu"
ENV THRESHOLD="0.5"

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
