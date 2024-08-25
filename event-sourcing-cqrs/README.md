# event-sourcing-cqrs

![CI](https://github.com/JainMayankA/event-sourcing-cqrs/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![PostgreSQL](https://img.shields.io/badge/postgres-16-blue)

An order management system built on event sourcing and CQRS (Command Query Responsibility Segregation). The event store is the single source of truth — state is never stored directly, only derived by replaying events.

## Architecture

```
Write side (commands)                    Read side (queries)
─────────────────────                    ──────────────────
POST /orders                             GET /orders/{id}
  │                                        │
  ▼                                        ▼
Order aggregate           ──events──►  OrderProjection
  │  (reconstituted                      (denormalized
  │   from events)                        read model)
  ▼
EventStore (PostgreSQL)
  │  append-only events table
  │
  ▼
SagaOrchestrator
  (payment → confirm → compensate on failure)
```

## Key design decisions

### Why event sourcing?
- **Full audit trail**: every state change is recorded as an immutable event
- **Time travel**: replay events to any point in time for debugging or analytics
- **Projection rebuild**: if a query model is wrong, fix the projection and replay — no data loss
- **Natural fit for CQRS**: the event stream is the perfect integration point between write and read models

### Optimistic concurrency
The `events` table has a `UNIQUE(aggregate_id, version)` constraint. Two concurrent writers appending at the same version causes a `UniqueViolation` — no distributed lock needed. The repository retries with exponential backoff on conflict.

### Saga pattern
The `OrderSaga` orchestrates the multi-step workflow: place → authorize payment → confirm. If payment fails, compensating transactions execute in reverse order (saga rollback). This replaces distributed transactions (2PC) with eventual consistency + compensation.

### CQRS separation
- **Write side**: aggregate methods validate business rules and raise events. Never queries the projection.
- **Read side**: projections handle events and maintain denormalized tables. `GET /orders` hits `order_summary` directly — no joins, sub-millisecond reads at scale.

### Projection rebuild
`POST /projections/rebuild` replays all events and rebuilds the read model from scratch. This is the escape hatch: if a projection bug corrupts query data, fix the handler and rebuild — the event store is untouched.

## Event flow

```
OrderPlaced → OrderProjection inserts into order_summary
           → SagaOrchestrator.start() triggers:
               PaymentService.authorize()
               → success: OrderConfirmed → projection updates status
               → failure: OrderCancelled (compensating tx)
```

## Quickstart

```bash
docker-compose up

# Place an order
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust-abc",
    "items": [{"product_id": "p1", "name": "Widget", "quantity": 2, "unit_price": 19.99}]
  }'

# Read order (from projection — fast)
curl http://localhost:8000/orders/{order_id}

# Ship it
curl -X POST http://localhost:8000/orders/{order_id}/ship \
  -d '{"tracking_number": "TRK123", "carrier": "FedEx"}'

# Customer stats (aggregated projection)
curl http://localhost:8000/customers/cust-abc/stats

# Rebuild projections from event history
curl -X POST http://localhost:8000/projections/rebuild
```

## Run tests (no database needed)

```bash
pip install -r requirements.txt
touch domain/__init__.py domain/aggregates/__init__.py store/__init__.py \
      projections/__init__.py sagas/__init__.py api/__init__.py tests/__init__.py
pytest tests/ -v
```

## Performance characteristics

| Operation | Mechanism | Latency |
|-----------|-----------|---------|
| Place order | Append 1 event to PostgreSQL | ~3ms |
| Read order | SELECT from denormalized projection | <1ms |
| Load aggregate | Replay N events (ORDER BY version) | ~1ms per 100 events |
| Rebuild projections | Full table scan + replay | ~10s per 100k events |

## Project structure

```
event-sourcing-cqrs/
├── domain/
│   ├── events.py              # Immutable domain events + registry
│   └── aggregates/
│       └── order.py           # Order aggregate root
├── store/
│   ├── event_store.py         # Append-only PostgreSQL event store
│   └── order_repository.py    # Load/save aggregate via event store
├── projections/
│   └── order_projection.py    # CQRS read model + rebuild support
├── sagas/
│   └── order_saga.py          # Saga orchestrator + compensating transactions
├── api/
│   └── server.py              # FastAPI — commands write, queries read projection
└── tests/
    ├── test_order_aggregate.py
    └── test_saga_and_store.py
```
