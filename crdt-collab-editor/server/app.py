"""
FastAPI application — HTTP REST + WebSocket endpoints.
"""

from __future__ import annotations
import logging
import os
import uuid

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from server.websocket_handler import handle_websocket, manager

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="CRDT Collaborative Editor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", **manager.stats()}


@app.get("/docs/new")
def create_doc():
    """Create a new document and return its ID."""
    doc_id = str(uuid.uuid4())[:8]
    return {"doc_id": doc_id, "ws_url": f"/ws/{doc_id}"}


@app.websocket("/ws/{doc_id}")
async def websocket_endpoint(websocket: WebSocket, doc_id: str):
    await handle_websocket(websocket, doc_id)


@app.get("/", response_class=HTMLResponse)
def demo_client():
    """Minimal browser demo client for quick testing."""
    return HTMLResponse(content=DEMO_HTML)


# Minimal vanilla-JS demo client embedded in the server response
DEMO_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>CRDT Collab Editor</title>
  <style>
    body { font-family: monospace; padding: 20px; max-width: 800px; }
    #editor { width: 100%; height: 300px; font-size: 16px; padding: 8px; border: 1px solid #ccc; }
    #presence { margin-top: 8px; font-size: 13px; color: #666; }
    #status { font-size: 12px; color: #999; margin-top: 4px; }
  </style>
</head>
<body>
  <h2>CRDT Collaborative Editor</h2>
  <div id="presence">Connecting...</div>
  <textarea id="editor" placeholder="Start typing..."></textarea>
  <div id="status">Disconnected</div>
  <script>
    const docId = location.hash.slice(1) || Math.random().toString(36).slice(2,10);
    location.hash = docId;
    const username = prompt("Your name:", "User" + Math.floor(Math.random()*100));
    const ws = new WebSocket(`ws://${location.host}/ws/${docId}`);
    const editor = document.getElementById("editor");
    let applying = false;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "join", username, doc_id: docId }));
      document.getElementById("status").textContent = "Connected to " + docId;
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "full_sync") {
        applying = true;
        editor.value = msg.text;
        applying = false;
      }
      if (msg.event === "op" && msg.data.type === "insert") {
        applying = true;
        const s = editor.selectionStart;
        const idx = msg.data.index || 0;
        editor.value = editor.value.slice(0,idx) + msg.data.char + editor.value.slice(idx);
        editor.selectionStart = editor.selectionEnd = s + (idx <= s ? 1 : 0);
        applying = false;
      }
      if (msg.event === "presence") {
        document.getElementById("presence").textContent =
          "Online: " + msg.clients.map(c => c.username).join(", ");
      }
    };

    let lastVal = "";
    editor.addEventListener("input", () => {
      if (applying) return;
      const val = editor.value;
      const pos = editor.selectionStart - 1;
      if (val.length > lastVal.length) {
        ws.send(JSON.stringify({ type: "op", data: { type: "insert", char: val[pos], index: pos, op_id: Date.now().toString(), site_id: username } }));
      }
      lastVal = val;
    });
  </script>
</body>
</html>"""
