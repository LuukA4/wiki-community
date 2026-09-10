const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");

const app = express();
const PORT = 3000;

const HEARTBEAT_TTL_MS = 20 * 60 * 1000;
const LOCK_TTL_MS = 30 * 60 * 1000;
const LOCK_CLEANUP_INTERVAL_MS = 60 * 1000;

const peers = {};
const locks = {};

app.use(cors());
app.use(bodyParser.json());

function now() {
  return Date.now();
}

function isActivePeer(peer) {
  return peer && now() - peer.lastSeen <= HEARTBEAT_TTL_MS;
}

function hasActiveLock(documentId) {
  const lock = locks[documentId];
  return lock && now() - lock.createdAt <= LOCK_TTL_MS;
}

function generateLockKey(documentId, peerId) {
  return `${documentId}:${peerId}:${now().toString(36)}`;
}

app.post("/register-peer", (req, res) => {
  const { peerId, address } = req.body || {};

  if (!peerId || !address) {
    return res.status(400).json({
      error: "Missing required fields: peerId and address are required."
    });
  }

  peers[peerId] = {
    peerId,
    address,
    lastSeen: now()
  };

  console.log(`[register-peer] Registered peer ${peerId} at ${address}`);
  return res.status(200).json({ message: "Peer registered", peerId });
});

app.post("/heartbeat", (req, res) => {
  const { peerId } = req.body || {};

  if (!peerId) {
    return res.status(400).json({
      error: "Missing required field: peerId is required."
    });
  }

  if (!peers[peerId]) {
    return res.status(404).json({ error: "Peer not registered. Call /register-peer first." });
  }

  peers[peerId].lastSeen = now();
  console.log(`[heartbeat] Peer ${peerId} heartbeat updated`);
  return res.status(200).json({ message: "Heartbeat received", peerId });
});

app.get("/active-peers", (req, res) => {
  const active = Object.values(peers)
    .filter(isActivePeer)
    .map((peer) => peer.peerId);

  return res.status(200).json({ peers: active });
});

app.post("/request-lock", (req, res) => {
  const { documentId, peerId } = req.body || {};

  if (!documentId || !peerId) {
    return res.status(400).json({
      error: "Missing required fields: documentId and peerId are required."
    });
  }

  if (hasActiveLock(documentId)) {
    const existing = locks[documentId];
    console.log(`[request-lock] Lock denied for document ${documentId} (held by ${existing.peerId})`);
    return res.status(400).json({
      error: "Document is already locked",
      documentId,
      lockedBy: existing.peerId,
      lockKey: existing.lockKey
    });
  }

  const lockKey = generateLockKey(documentId, peerId);
  locks[documentId] = {
    documentId,
    peerId,
    lockKey,
    createdAt: now()
  };

  console.log(`[request-lock] Lock granted for document ${documentId} to peer ${peerId} (key: ${lockKey})`);
  return res.status(200).json({ lockKey });
});

function cleanupExpiredLocks() {
  for (const documentId of Object.keys(locks)) {
    const lock = locks[documentId];
    if (now() - lock.createdAt > LOCK_TTL_MS) {
      console.log(`[cleanup] Releasing expired lock for document ${documentId} (held by ${lock.peerId})`);
      delete locks[documentId];
    }
  }
}

setInterval(cleanupExpiredLocks, LOCK_CLEANUP_INTERVAL_MS);

app.listen(PORT, () => {
  console.log(`Oracle server running on http://localhost:${PORT}`);
  console.log(`Lock cleanup runs every ${LOCK_CLEANUP_INTERVAL_MS / 1000}s; locks expire after ${LOCK_TTL_MS / 60000} minutes.`);
});

/*
 * ============================================================
 * Testinstructies (curl)
 * ============================================================
 *
 * 1. Server starten:
 *    node server.js
 *
 * 2. Peer registreren:
 *    curl -X POST http://localhost:3000/register-peer \
 *      -H "Content-Type: application/json" \
 *      -d '{"peerId":"peer-1","address":"192.168.1.10:5000"}'
 *
 * 3. Heartbeat sturen:
 *    curl -X POST http://localhost:3000/heartbeat \
 *      -H "Content-Type: application/json" \
 *      -d '{"peerId":"peer-1"}'
 *
 * 4. Actieve peers ophalen:
 *    curl -X GET http://localhost:3000/active-peers
 *
 * 5. Lock aanvragen:
 *    curl -X POST http://localhost:3000/request-lock \
 *      -H "Content-Type: application/json" \
 *      -d '{"documentId":"doc-42","peerId":"peer-1"}'
 *
 * 6. Lock opnieuw aanvragen (zal falen met 400):
 *    curl -X POST http://localhost:3000/request-lock \
 *      -H "Content-Type: application/json" \
 *      -d '{"documentId":"doc-42","peerId":"peer-2"}'
 *
 * 7. Foutafhandeling testen (ontbrekende velden):
 *    curl -X POST http://localhost:3000/register-peer \
 *      -H "Content-Type: application/json" \
 *      -d '{"peerId":"peer-1"}'
 *
 * 8. Foutafhandeling heartbeat voor ongeregistreerde peer:
 *    curl -X POST http://localhost:3000/heartbeat \
 *      -H "Content-Type: application/json" \
 *      -d '{"peerId":"ghost-peer"}'
 */
