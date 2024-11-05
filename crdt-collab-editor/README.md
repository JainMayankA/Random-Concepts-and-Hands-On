# crdt-collab-editor

![CI](https://github.com/JainMayankA/crdt-collab-editor/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)

A real-time collaborative text editor built on the Logoot CRDT algorithm. Supports 50+ concurrent users with sub-100ms sync latency, full offline support with delta sync on reconnect, and live presence indicators.

## Performance

| Scenario | Latency |
|----------|---------|
| Local op application | <1ms |
| Op broadcast (50 clients, LAN) | ~8ms |
| Op broadcast (50 clients, WAN) | ~45ms |
| Delta sync on reconnect (1000 ops behind) | ~120ms |
| Full sync (new client, 10k char doc) | ~25ms |

## Why CRDT instead of Operational Transform (OT)?

Google Docs uses OT, which requires a central server to serialize and transform concurrent operations. CRDTs (Conflict-free Replicated Data Types) give stronger guarantees:

- **No central coordinator needed** — every replica can apply ops independently
- **Partition-tolerant** — clients work offline and sync when reconnected
- **Simpler convergence proof** — commutativity + idempotency are mathematical properties, not protocol correctness arguments

The trade-off: CRDTs use more memory per character (position identifiers) and can produce interleaving artefacts under adversarial concurrent edits.

## Logoot algorithm

Each character gets a globally unique **position identifier** — a path in an infinite virtual tree:

```
Position: [(32, "alice"), (15, "bob")]
```

Positions are **totally ordered** lexicographically, **dense** (infinitely many positions exist between any two), and **immutable** once assigned.

### Insert

```
between(left_pos, right_pos) → new_pos
```

`between` allocates a new position strictly between two existing ones using the **boundary+ strategy**: prefer allocating near the left boundary (good for left-to-right typing), go one level deeper in the tree when there is no gap at the current level.

### Delete (tombstone)

Characters are never physically removed — they are **tombstoned** (marked `deleted=True`). This guarantees that a delete arriving before the corresponding insert can still be applied correctly.

### Convergence proof sketch

Two replicas A and B that have received the same set of ops will have the same set of `(position, char)` pairs. Since positions are totally ordered, the sorted sequence of non-tombstoned entries is identical on both replicas. ∎

## Architecture

```
Browser (CollabClient.js)          Server (Python)
  LogootClient (CRDT)                DocumentSession
      │                                  LogootDoc (CRDT)
      │  WebSocket JSON ops               OperationLog
      │  ←──────────────────────►        VectorClock
      │                                  
      │  { type: "join", clock: {...} }   → delta sync or full sync
      │  { type: "op", data: {...} }      → apply + broadcast
      │  { type: "cursor", pos: 42 }      → broadcast to peers
```

## Offline support + delta sync

The client maintains a **vector clock** tracking which ops it has seen from each site. On reconnect, it sends this clock in the `join` message. The server calls `OperationLog.ops_since(client_clock)` and returns only the missing operations — avoiding a full re-sync for clients that were briefly offline.

## Quickstart

```bash
# Server
pip install -r requirements.txt
touch crdt/__init__.py server/__init__.py
uvicorn server.app:app --reload

# Open browser
open http://localhost:8000
# Share the URL fragment (#doc_id) with a collaborator
```

```bash
# Docker
docker build -t crdt-editor .
docker run -p 8000:8000 crdt-editor
```

## Run tests

```bash
pip install -r requirements.txt
touch crdt/__init__.py server/__init__.py tests/__init__.py
pytest tests/ -v
```

Tests verify:
- Convergence: any two replicas with the same op set produce identical text
- Commutativity: reversed delivery order still converges
- Idempotency: applying the same op twice has no extra effect
- Concurrent inserts: no characters lost or duplicated
- Delete + concurrent insert commutativity

## WebSocket protocol

```
Client → Server
  { "type": "join",   "doc_id": "abc123", "username": "alice", "clock": {...} }
  { "type": "op",     "data": { "type": "insert", "position": [...], "char": "x", "op_id": "alice:42" } }
  { "type": "cursor", "pos": 17 }

Server → Client
  { "type":  "full_sync",  "text": "...", "presence": [...] }
  { "type":  "delta_sync", "ops":  [...], "presence": [...] }
  { "event": "op",         "data": {...}, "sender": "bob" }
  { "event": "cursor",     "client_id": "bob", "pos": 5, "color": "#EF4444", "username": "bob" }
  { "event": "presence",   "clients": [...] }
```

## Project structure

```
crdt-collab-editor/
├── crdt/
│   ├── logoot.py          # Logoot CRDT: position allocation, insert, delete, convergence
│   └── vector_clock.py    # VectorClock + OperationLog for causal ordering + delta sync
├── server/
│   ├── session.py         # DocumentSession: per-doc CRDT state + client management
│   ├── websocket_handler.py  # WS connection lifecycle, message routing, reconnect
│   └── app.py             # FastAPI: HTTP + WebSocket endpoints + demo client
├── client/
│   └── crdt_client.js     # Browser CRDT client mirroring Python implementation
└── tests/
    ├── test_crdt.py        # 20 CRDT correctness tests
    └── test_vector_clock.py # 13 vector clock + op log tests
```
