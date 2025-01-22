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

from psycopg2 import pool as pgpool
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from domain.aggregates.order import Order
from store.event_store import EventStore
from store.order_repository import OrderRepository, OrderNotFoundError
from projections.order_projection import OrderProjection
from sagas.order_saga import SagaOrchestrator, OrderService, PaymentService

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Order Management — Event Sourcing + CQRS", version="1.0.0")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/orders")

_pool: pgpool.ThreadedConnectionPool = None


@app.on_event("startup")
def startup():
    global _pool
    _pool = pgpool.ThreadedConnectionPool(
        minconn=2,
        maxconn=20,
        dsn=DATABASE_URL,
    )


@app.on_event("shutdown")
def shutdown():
    if _pool:
        _pool.closeall()


def get_connection():
    if _pool is None:
        raise RuntimeError("Database connection pool has not been initialized")
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def get_deps(conn=Depends(get_connection)):
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
def place_order(req: PlaceOrderRequest, deps=Depends(get_deps)):
    repo, _, _, _ = deps
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


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, req: ShipOrderRequest, deps=Depends(get_deps)):
    repo, _, _, _ = deps
    order = _load_or_404(repo, order_id)
    order.ship(req.tracking_number, req.carrier)
    repo.save(order)
    return {"order_id": order_id, "status": order.status, "tracking": req.tracking_number}


@app.post("/orders/{order_id}/deliver")
def deliver_order(order_id: str, deps=Depends(get_deps)):
    repo, _, _, _ = deps
    order = _load_or_404(repo, order_id)
    order.deliver()
    repo.save(order)
    return {"order_id": order_id, "status": order.status}


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, req: CancelOrderRequest, deps=Depends(get_deps)):
    repo, _, _, _ = deps
    order = _load_or_404(repo, order_id)
    order.cancel(req.reason)
    repo.save(order)
    return {"order_id": order_id, "status": order.status}


# ── Read endpoints (queries — hit projection, not event store) ────────────────

@app.get("/orders/{order_id}")
def get_order(order_id: str, deps=Depends(get_deps)):
    _, projection, _, _ = deps
    order = projection.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/orders")
def list_orders(
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    deps=Depends(get_deps),
):
    _, projection, _, _ = deps
    return projection.list_orders(customer_id, status, limit, offset)


@app.get("/customers/{customer_id}/stats")
def customer_stats(customer_id: str, deps=Depends(get_deps)):
    _, projection, _, _ = deps
    stats = projection.get_customer_stats(customer_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Customer not found")
    return stats


@app.post("/projections/rebuild")
def rebuild_projections(deps=Depends(get_deps)):
    """Replay all events and rebuild read models from scratch."""
    _, projection, store, conn = deps
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT aggregate_id FROM events ORDER BY aggregate_id")
        ids = [row[0] for row in cur.fetchall()]
    all_events = []
    for agg_id in ids:
        all_events.extend(store.load(agg_id))
    all_events.sort(key=lambda e: e.occurred_at)
    projection.rebuild(all_events)
    return {"rebuilt": True, "events_replayed": len(all_events), "aggregates": len(ids)}


@app.get("/health")
def health():
    return {"status": "ok"}


def _load_or_404(repo: OrderRepository, order_id: str) -> Order:
    try:
        return repo.load(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
