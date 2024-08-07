"""
REST API — thin layer over commands and queries.
Write endpoints call aggregate methods → repository.save().
Read endpoints call projection query methods directly.
No business logic lives here.
"""

import os
import uuid
import logging
from typing import Optional

import psycopg2
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from domain.aggregates.order import Order
from store.event_store import EventStore
from store.order_repository import OrderRepository, OrderNotFoundError
from projections.order_projection import OrderProjection
from sagas.order_saga import SagaOrchestrator, OrderService, PaymentService

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Order Management — Event Sourcing + CQRS", version="1.0.0")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/orders")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def get_deps():
    conn = get_conn()
    store = EventStore(conn)
    projection = OrderProjection(conn)
    repo = OrderRepository(store, projections=[projection])
    return repo, projection, store, conn


# ── Request/response schemas ──────────────────────────────────────────────────

class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float


class PlaceOrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem]


class ShipOrderRequest(BaseModel):
    tracking_number: str
    carrier: str


class CancelOrderRequest(BaseModel):
    reason: str


# ── Write endpoints (commands) ────────────────────────────────────────────────

@app.post("/orders", status_code=201)
def place_order(req: PlaceOrderRequest):
    repo, projection, store, conn = get_deps()
    try:
        order_id = str(uuid.uuid4())
        items = [i.model_dump() for i in req.items]
        order = Order.place(order_id, req.customer_id, items)

        saga_orch = SagaOrchestrator(
            order_service=OrderService(repo),
            payment_service=PaymentService(),
        )
        repo.save(order)
        total = order.total_amount
        saga = saga_orch.start_order_saga(order_id, req.customer_id, total)

        return {"order_id": order_id, "status": order.status, "saga_state": saga.state}
    finally:
        conn.close()


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, req: ShipOrderRequest):
    repo, _, _, conn = get_deps()
    try:
        order = _load_or_404(repo, order_id)
        order.ship(req.tracking_number, req.carrier)
        repo.save(order)
        return {"order_id": order_id, "status": order.status, "tracking": req.tracking_number}
    finally:
        conn.close()


@app.post("/orders/{order_id}/deliver")
def deliver_order(order_id: str):
    repo, _, _, conn = get_deps()
    try:
        order = _load_or_404(repo, order_id)
        order.deliver()
        repo.save(order)
        return {"order_id": order_id, "status": order.status}
    finally:
        conn.close()


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, req: CancelOrderRequest):
    repo, _, _, conn = get_deps()
    try:
        order = _load_or_404(repo, order_id)
        order.cancel(req.reason)
        repo.save(order)
        return {"order_id": order_id, "status": order.status}
    finally:
        conn.close()


# ── Read endpoints (queries — hit projection, not event store) ────────────────

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    _, projection, _, conn = get_deps()
    try:
        order = projection.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    finally:
        conn.close()


@app.get("/orders")
def list_orders(
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    _, projection, _, conn = get_deps()
    try:
        return projection.list_orders(customer_id, status, limit, offset)
    finally:
        conn.close()


@app.get("/customers/{customer_id}/stats")
def customer_stats(customer_id: str):
    _, projection, _, conn = get_deps()
    try:
        stats = projection.get_customer_stats(customer_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Customer not found")
        return stats
    finally:
        conn.close()


@app.post("/projections/rebuild")
def rebuild_projections():
    """Replay all events and rebuild read models from scratch."""
    repo, projection, store, conn = get_deps()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT aggregate_id FROM events ORDER BY aggregate_id")
            ids = [row[0] for row in cur.fetchall()]
        all_events = []
        for agg_id in ids:
            all_events.extend(store.load(agg_id))
        all_events.sort(key=lambda e: e.occurred_at)
        projection.rebuild(all_events)
        return {"rebuilt": True, "events_replayed": len(all_events), "aggregates": len(ids)}
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}


def _load_or_404(repo: OrderRepository, order_id: str) -> Order:
    try:
        return repo.load(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
