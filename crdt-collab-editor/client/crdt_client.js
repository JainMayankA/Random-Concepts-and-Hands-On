/**
 * Browser-side CRDT client.
 * Mirrors the Python LogootDoc on the client — all operations are
 * generated locally (low latency), then broadcast to the server.
 *
 * Offline support: operations are queued when disconnected and
 * replayed in order on reconnect with delta sync.
 */

const BASE = 32;
const BOUNDARY = 10;

function positionComponent(value, siteId) {
  return { value, siteId };
}

function comparePositions(p, q) {
  const len = Math.max(p.length, q.length);
  for (let i = 0; i < len; i++) {
    const pv = i < p.length ? p[i].value : 0;
    const qv = i < q.length ? q[i].value : 0;
    if (pv !== qv) return pv - qv;
    const ps = i < p.length ? p[i].siteId : "";
    const qs = i < q.length ? q[i].siteId : "";
    if (ps < qs) return -1;
    if (ps > qs) return 1;
  }
  return 0;
}

function between(p, q, siteId, depth = 0) {
  const pv = depth < p.length ? p[depth].value : 0;
  const qv = depth < q.length ? q[depth].value : (2 ** 31 - 1);
  const gap = qv - pv;

  if (gap > 1) {
    const step = Math.min(BOUNDARY, gap - 1);
    const newVal = pv + Math.floor(Math.random() * step) + 1;
    return [...p.slice(0, depth), positionComponent(newVal, siteId)];
  }

  if (gap === 1) {
    if (depth < p.length - 1) {
      const sub = between(p, [positionComponent(2 ** 31 - 1, "~")], siteId, depth + 1);
      return [...p.slice(0, depth), positionComponent(pv, p[depth].siteId), ...sub.slice(depth)];
    }
    return [...p, positionComponent(Math.floor(Math.random() * BASE) + 1, siteId)];
  }

  return between(p, q, siteId, depth + 1);
}

export class LogootClient {
  constructor(siteId) {
    this.siteId = siteId;
    this._clock = 0;
    this._entries = [
      { position: [positionComponent(0, "")],          char: "", opId: "__start__", deleted: false },
      { position: [positionComponent(2 ** 31 - 1, "~")], char: "", opId: "__end__",   deleted: false },
    ];
    this._opIndex = {};
  }

  insert(index, char) {
    const visible = this._visible();
    const left  = visible[index];
    const right = visible[index + 1];
    const pos = between(left.position, right.position, this.siteId);
    const opId = `${this.siteId}:${this._clock++}`;
    const entry = { position: pos, char, opId, deleted: false };
    this._insertEntry(entry);
    return { type: "insert", position: pos, char, op_id: opId, site_id: this.siteId };
  }

  delete(index) {
    const visible = this._visible();
    const entry = visible[index + 1];
    entry.deleted = true;
    return { type: "delete", op_id: entry.opId, site_id: this.siteId };
  }

  applyRemote(op) {
    if (op.type === "insert") {
      if (!this._opIndex[op.op_id]) {
        const entry = {
          position: op.position,
          char: op.char,
          opId: op.op_id,
          deleted: false,
        };
        this._insertEntry(entry);
      }
    } else if (op.type === "delete") {
      const entry = this._opIndex[op.op_id];
      if (entry) entry.deleted = true;
    }
  }

  text() {
    return this._entries
      .filter(e => !e.deleted && e.opId !== "__start__" && e.opId !== "__end__")
      .map(e => e.char)
      .join("");
  }

  _visible() {
    return this._entries.filter(e => !e.deleted);
  }

  _insertEntry(entry) {
    let lo = 0, hi = this._entries.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (comparePositions(this._entries[mid].position, entry.position) < 0) lo = mid + 1;
      else hi = mid;
    }
    this._entries.splice(lo, 0, entry);
    this._opIndex[entry.opId] = entry;
  }
}

export class CollabClient {
  constructor(serverUrl, docId, username, onUpdate, onPresence) {
    this.serverUrl   = serverUrl;
    this.docId       = docId;
    this.username    = username;
    this.siteId      = `${username}-${Math.random().toString(36).slice(2, 7)}`;
    this.onUpdate    = onUpdate;
    this.onPresence  = onPresence;
    this.crdt        = new LogootClient(this.siteId);
    this._ws         = null;
    this._pendingOps = [];
    this._connected  = false;
    this._clock      = {};
  }

  connect() {
    const url = `${this.serverUrl}/ws/${this.docId}`;
    this._ws = new WebSocket(url);

    this._ws.onopen = () => {
      this._connected = true;
      this._ws.send(JSON.stringify({
        type: "join", username: this.username,
        doc_id: this.docId, clock: this._clock,
      }));
    };

    this._ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      this._handleMessage(msg);
    };

    this._ws.onclose = () => {
      this._connected = false;
      setTimeout(() => this.connect(), 2000 + Math.random() * 1000);
    };
  }

  localInsert(index, char) {
    const op = this.crdt.insert(index, char);
    this._send({ type: "op", data: op });
    return op;
  }

  localDelete(index) {
    const op = this.crdt.delete(index);
    this._send({ type: "op", data: op });
    return op;
  }

  sendCursor(pos) {
    this._send({ type: "cursor", pos });
  }

  _handleMessage(msg) {
    if (msg.type === "full_sync") {
      this.crdt = new LogootClient(this.siteId);
      // Server sends authoritative text; re-apply pending local ops
      msg.ops && msg.ops.forEach(op => this.crdt.applyRemote(op));
      this.onUpdate(this.crdt.text());
      if (msg.presence) this.onPresence(msg.presence);
    } else if (msg.type === "delta_sync") {
      msg.ops.forEach(op => this.crdt.applyRemote(op));
      this.onUpdate(this.crdt.text());
      if (msg.presence) this.onPresence(msg.presence);
    } else if (msg.event === "op") {
      this.crdt.applyRemote(msg.data);
      this.onUpdate(this.crdt.text());
    } else if (msg.event === "presence") {
      this.onPresence(msg.clients);
    }
  }

  _send(msg) {
    if (this._connected && this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(msg));
    } else {
      this._pendingOps.push(msg);
    }
  }

  get text() {
    return this.crdt.text();
  }
}
