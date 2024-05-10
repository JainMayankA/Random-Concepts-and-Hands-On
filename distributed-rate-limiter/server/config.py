import os
from dataclasses import dataclass, field


@dataclass
class Config:
    redis_url: str = "redis://localhost:6379/0"
    grpc_port: int = 50051
    max_workers: int = 20
    metrics_port: int = 8000

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            grpc_port=int(os.getenv("GRPC_PORT", "50051")),
            max_workers=int(os.getenv("MAX_WORKERS", "20")),
            metrics_port=int(os.getenv("METRICS_PORT", "8000")),
        )
