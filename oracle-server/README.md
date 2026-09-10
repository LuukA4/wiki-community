# Oracle Server

Een minimale, maar functionele Oracle-server in Node.js voor een gedecentraliseerd peer-to-peer documentbeheersysteem. De server beheert peer-registratie, heartbeats, actieve peers en locks voor documentbewerkingen, met een in-memory database.

## Functionaliteit

- **Peer Registratie** — `POST /register-peer`
- **Heartbeat** — `POST /heartbeat`
- **Actieve Peers** — `GET /active-peers` (peers met een heartbeat in de laatste 20 minuten)
- **Lock Aanvragen** — `POST /request-lock` (locks zijn 30 minuten geldig)
- **Automatische lock-vrijgave** — om de minuut worden verlopen locks opgeruimd

## Vereisten

- [Node.js](https://nodejs.org/) (18+ aanbevolen)

## Installatie

```bash
cd oracle-server
npm install
```

## Server starten

```bash
node server.js
```

De server draait op `http://localhost:3000`. CORS is ingeschakeld voor lokale tests.

## Testen met curl

### 1. Peer registreren
```bash
curl -X POST http://localhost:3000/register-peer \
  -H "Content-Type: application/json" \
  -d '{"peerId":"peer-1","address":"192.168.1.10:5000"}'
```
Verwacht: `{"message":"Peer registered","peerId":"peer-1"}`

### 2. Heartbeat sturen
```bash
curl -X POST http://localhost:3000/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"peerId":"peer-1"}'
```
Verwacht: `{"message":"Heartbeat received","peerId":"peer-1"}`

### 3. Actieve peers ophalen
```bash
curl -X GET http://localhost:3000/active-peers
```
Verwacht: `{"peers":["peer-1"]}`

### 4. Lock aanvragen
```bash
curl -X POST http://localhost:3000/request-lock \
  -H "Content-Type: application/json" \
  -d '{"documentId":"doc-42","peerId":"peer-1"}'
```
Verwacht: `{"lockKey":"doc-42:peer-1:<timestamp>"}`

### 5. Lock opnieuw aanvragen (zal falen met 400)
```bash
curl -X POST http://localhost:3000/request-lock \
  -H "Content-Type: application/json" \
  -d '{"documentId":"doc-42","peerId":"peer-2"}'
```
Verwacht: `400 Bad Request` met `{"error":"Document is already locked", ...}`

### 6. Foutafhandeling testen (ontbrekende velden)
```bash
curl -X POST http://localhost:3000/register-peer \
  -H "Content-Type: application/json" \
  -d '{"peerId":"peer-1"}'
```
Verwacht: `400 Bad Request` met `{"error":"Missing required fields: peerId and address are required."}`

### 7. Heartbeat voor ongeregistreerde peer
```bash
curl -X POST http://localhost:3000/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"peerId":"ghost-peer"}'
```
Verwacht: `404 Not Found` met `{"error":"Peer not registered. Call /register-peer first."}`

## Configuratie

De volgende constanten zijn gedefinieerd in `server.js` en kunnen worden aangepast:

| Constante | Standaardwaarde | Omschrijving |
|---|---|---|
| `PORT` | `3000` | Poort waarop de server luistert |
| `HEARTBEAT_TTL_MS` | `20 minuten` | Tijd waarna een peer als inactief wordt beschouwd |
| `LOCK_TTL_MS` | `30 minuten` | Geldigheidsduur van een lock |
| `LOCK_CLEANUP_INTERVAL_MS` | `1 minuut` | Interval voor het opruimen van verlopen locks |
