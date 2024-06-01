FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ proto/
COPY server/ server/
COPY client/ client/

RUN python -m grpc_tools.protoc \
    -I proto \
    --python_out=proto \
    --grpc_python_out=proto \
    proto/ratelimiter.proto

RUN touch proto/__init__.py server/__init__.py client/__init__.py

CMD ["python", "-m", "server.grpc_server"]
