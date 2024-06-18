"""
Dashboard REST API.

Serves live metrics and anomaly history from ClickHouse for the
frontend dashboard. All reads hit ClickHouse directly — sub-second
even over millions of rows thanks to columnar storage + indexing.
"""

from __future__ import annotations
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from pipeline.clickhouse_writer import ClickHouseWriter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Streaming Anomaly Pipeline — Dashboard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_writer: Optional[ClickHouseWriter] = None


def get_writer() -> ClickHouseWriter:
    global _writer
    if _writer is None:
        _writer = ClickHouseWriter.from_env()
    return _writer


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/anomalies/recent")
def recent_anomalies(hours: int = Query(1, ge=1, le=72)):
    """Return anomaly events from the last N hours, ordered by recency."""
    try:
        return get_writer().query_recent_anomalies(hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anomalies/rate")
def anomaly_rate(minutes: int = Query(60, ge=5, le=1440)):
    """Return anomaly counts per metric for the last N minutes."""
    try:
        return get_writer().anomaly_rate(minutes=minutes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics/series")
def metric_series(
    metric_name: str = Query(...),
    host: str = Query(...),
    minutes: int = Query(60, ge=1, le=1440),
    step_seconds: int = Query(10, ge=1, le=3600),
):
    """
    Return time-bucketed metric values for charting.
    Uses ClickHouse's toStartOfInterval() for server-side bucketing —
    much faster than fetching raw rows and aggregating in Python.
    """
    try:
        return get_writer().query_metric_series(
            metric_name=metric_name,
            host=host,
            minutes=minutes,
            step_seconds=step_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics/summary")
def metrics_summary():
    """
    Quick stats for the dashboard header: total anomalies in last hour,
    breakdown by severity proxy (z_score > 5 = critical).
    """
    try:
        writer = get_writer()
        recent = writer.query_recent_anomalies(hours=1, limit=1000)
        critical = sum(1 for r in recent if abs(r.get("z_score", 0)) >= 5)
        warning  = sum(1 for r in recent if 3 <= abs(r.get("z_score", 0)) < 5)
        return {
            "total_anomalies_1h": len(recent),
            "critical": critical,
            "warning": warning,
            "info": len(recent) - critical - warning,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
