"""
Pipeline entrypoint — wires together all components.

Topology:
  Kafka (metrics topic)
    → MetricConsumer (batching)
      → StreamingAnomalyDetector (Isolation Forest)
        → ClickHouseWriter (persistence)
        → AlertDispatcher (notifications)

Run:
    python -m pipeline.main

Or with load generator:
    python -m pipeline.main --with-producer
"""

from __future__ import annotations
import argparse
import logging
import os
import threading

from pipeline.consumer import MetricConsumer, MetricBatch
from pipeline.clickhouse_writer import ClickHouseWriter
from pipeline.alert_dispatcher import AlertDispatcher
from detector.isolation_forest import StreamingAnomalyDetector, DetectorConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def build_pipeline():
    writer     = ClickHouseWriter.from_env()
    dispatcher = AlertDispatcher()
    config     = DetectorConfig(
        contamination=float(os.getenv("CONTAMINATION", "0.05")),
        window_size=int(os.getenv("WINDOW_SIZE", "200")),
        retrain_interval=int(os.getenv("RETRAIN_INTERVAL", "500")),
    )
    detector = StreamingAnomalyDetector(config)

    def on_batch(batch: MetricBatch):
        results = detector.process_batch(
            metric_name=batch.metric_name,
            host=batch.host,
            region=batch.region,
            values=batch.values,
            timestamps=batch.timestamps,
        )

        # Write all results to ClickHouse metrics table
        metric_rows = [
            {
                "timestamp":   r.timestamp,
                "metric_name": r.metric_name,
                "host":        r.host,
                "region":      r.region,
                "value":       r.value,
                "z_score":     r.z_score,
                "window_mean": r.window_mean,
                "window_std":  r.window_std,
            }
            for r in results
        ]
        writer.write_metrics(metric_rows)

        # Handle anomalies
        for result in results:
            if result.is_anomaly:
                writer.write_anomaly({
                    "timestamp":     result.timestamp,
                    "metric_name":   result.metric_name,
                    "host":          result.host,
                    "region":        result.region,
                    "value":         result.value,
                    "anomaly_score": result.anomaly_score,
                    "z_score":       result.z_score,
                    "window_mean":   result.window_mean,
                    "window_std":    result.window_std,
                })
                dispatcher.dispatch(result)

    return MetricConsumer(
        bootstrap_servers=BOOTSTRAP,
        batch_window_seconds=float(os.getenv("BATCH_WINDOW_SECONDS", "5")),
        on_batch=on_batch,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-producer", action="store_true",
                        help="Also run the synthetic metric producer")
    args = parser.parse_args()

    if args.with_producer:
        from pipeline.producer import run_producer
        t = threading.Thread(
            target=run_producer,
            kwargs={"bootstrap_servers": BOOTSTRAP, "rate_per_second": 1000},
            daemon=True,
        )
        t.start()
        logger.info("Synthetic producer started")

    consumer = build_pipeline()
    logger.info("Pipeline running — Ctrl+C to stop")
    consumer.run()


if __name__ == "__main__":
    main()
