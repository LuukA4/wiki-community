# wiki-community

Automatische synchronisatie van de lore-documenten uit Google Drive naar de Firestore-database van de wiki-website. De documenten worden eerst door AI (Mistral) omgezet naar gestructureerde entiteiten (personages, landen, steden, tijdlijn, ...), die daarna als documenten in Firestore worden weggeschreven.

## Architectuur

```
Google Drive (map "Lore")
   │  service account, read-only, recursief (incl. submappen)
   ▼
lore_sync.drive_source      exporteert Docs → markdown, Sheets → CSV
   ▼
lore_sync.chunking          opschonen + in stukken knippen (per sectie, met overlap)
   ▼
lore_sync.extract           Mistral AI → gestructureerde JSON per entiteitstype
   │                          (lore_sync.schemas.py bevat het JSON-schema per type)
   ▼
lore_sync.merge             dedup/merge op slug van de naam; sources per entiteit bijgehouden
   ▼
lore_sync.firestore_sink    batched upserts (merge=True) met deterministische doc-ID = slug
   │                          + sync_state per bronbestand (modifiedTime) voor incrementeel sync
   ▼
Firestore (Firebase)
```

## Firestore-collecties

Standaard mapping (te wijzigen in `config/sources.json` → `entity_collections`):

| Entiteitstype | Collectie | Voorbeeldvelden |
|---|---|---|
| `character` | `personages` | naam, familie, functie, titels, loyaliteit, religie, geboorteplaats, sterfteplaats, informatie, sources |
| `country` | `landen` | naam, type, motto, hoofdstad, regeringsvorm, beschrijving |
| `region` | `regios` | naam, type, land, hoofdstad, beschrijving |
| `city` | `steden` | naam, land, regio, beschrijving, interessante_locaties |
| `timeline_event` | `tijdlijn` | jaar (negatief = vóór jaar 0), titel, detail, groep, kleur |
| `organization` | `organisaties` | naam, type, leider, locatie, leden, beschrijving |
| `deity` | `goden` | naam, titel, domeinen, beschrijving |
| `religion` | `religies` | naam, goden, beschrijving |
| `item` | `voorwerpen` | naam, type, eigenaar, beschrijving |

Daarnaast: `sync_state` (per Drive-bestand: `modifiedTime`, `processedAt`, `stats`) en `sync_runs` (per run een samenvatting). Bestanden met een ongewijzigde `modifiedTime` worden overgeslagen, tenzij `--force`.

Welke entiteitstypes uit welk document worden gehaald, staat in `config/sources.json` → `title_rules` (match op de bestandsnaam). Spreadsheets (zoals de tijdlijn) worden direct als CSV geparseerd naar `tijdlijn`.

## Setup

### 1. Google Drive-toegang (service account)

1. Maak een project in Google Cloud Console, zet de **Google Drive API** aan.
2. Maak een service account aan, download de JSON-key.
3. Deel de map "Lore" (en submappen) met het e-mailadres van het service account als **Viewer**.
4. Sla de key op als secret `GOOGLE_SERVICE_ACCOUNT_JSON` (inhoud van het JSON-bestand).

### 2. Firestore-toegang (service account)

1. In hetzelfde (of het Firebase-)project: **Settings → Service accounts → Generate new private key** (Firebase Admin SDK).
2. Zet in Firestore de collection-namen goed (zie tabel hierboven).
3. Secrets: `FIREBASE_SERVICE_ACCOUNT_JSON` (key-inhoud) en `FIREBASE_PROJECT_ID`.

### 3. Mistral AI

Maak een API-key aan op [console.mistral.ai](https://console.mistral.ai) → secret `MISTRAL_API_KEY`. Model instelbaar via `MISTRAL_MODEL` (standaard `mistral-large-latest`).

### 4. GitHub Actions (automatisering)

De workflow `.github/workflows/sync-lore.yml` draait wekelijks (zondag 03:00 UTC) en handmatig via **Run workflow** (standaard als dry run). Zet in de repo onder **Settings → Secrets and variables → Actions** de secrets: `MISTRAL_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`.

## Lokaal draaien

```bash
pip install -r requirements-dev.txt
export MISTRAL_API_KEY=...
export GOOGLE_SERVICE_ACCOUNT_JSON='$(cat service-account.json)'
export FIREBASE_PROJECT_ID=...
export FIREBASE_SERVICE_ACCOUNT_JSON='$(cat firebase-key.json)'

python -m lore_sync list                                  # toon Drive-bestanden
python -m lore_sync sync --dry-run                        # extractie zonder Firestore-writes
python -m lore_sync sync --types character timeline_event # alleen bepaalde types
python -m lore_sync sync --force                          # alles opnieuw
pytest                                                    # tests
```

Zonder Firestore-credentials kun je met `--dry-run` (of `DRY_RUN=true`) de extractie testen; de Firestore-secrets zijn dan niet nodig.

## Extending

- Nieuwe bronmap: voeg het folder-ID toe aan `folders` in `config/sources.json` (of `--folders`).
- Nieuw documenttype: voeg een regel toe aan `title_rules` en eventueel een schema in `lore_sync/schemas.py`.
- Bestaand entiteitstype uitbreiden: pas het schema in `lore_sync/schemas.py` aan; Firestore merge't nieuwe velden automatisch bij.
