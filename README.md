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
lore_sync.page_builder      entiteit → `pages`-document in het exacte formaat van de website:
   │                          doc-ID = titel met spaties→underscores, category, infoboxRows
   │                          ({cells: [label, waarde]}), infoboxCaption, content als Markdown
   │                          ({Naam} wiki-links uit Drive worden [[Naam]])
   ▼
lore_sync.firestore_sink    setDoc naar collectie `pages`; pagina's die al bestaan worden
   │                          overgeslagen (--force overschrijft); Admin SDK omzeilt de
   │                          security rules (bedoeld voor de bulk-import)
   │                          + sync_state per bronbestand (modifiedTime) voor incrementeel sync
   ▼
Firestore (project `the-lore-wiki`)
```

## Datamodel van de website (Legendarium)

De website leest uit Firestore (project `the-lore-wiki`):

- **`pages/{docId}`** — één document per wiki-pagina. `docId = title.replace(/\s+/g, '_')`. Velden: `title`, `content` (Markdown: koppen, **vet**, lijsten, `[[WikiLink]]`/`[[Doel|Tekst]]`, afbeeldingen `![alt](images/bestand){width=.. align=..}`), `category` (groep op de startpagina), `infoboxRows` (array van `{cells: [label, waarde, ...]}` — één object per rij), `infoboxCaption`, `updatedAt`.
- **`images/{bestandsnaam}`** — `name`, `data` (base64 data-URL, max ~700KB), `uploadedAt`.
- **`locks/page-{titel}`** — bewerk-vergrendeling (hartslag, TTL 5 min).
- **`editorRequests/{uid}`** —ferrer aanwezig = bewerkrechten (code gecheckt via rules tegen `settings/editor-code`).

De sync maakt hier **alleen `pages`-documenten** aan (plus `sync_state`/`sync_runs` voor de sync zelf). Bestaat een pagina al? Dan wordt hij overgeslagen, zodat handmatige wijzigingen in de website behouden blijven (`--force` overschrijft wel).

Mapping entiteitstype → categorie/caption staat in `config/sources.json` → `entity_pages`:

| Entiteitstype | Categorie (startpagina) | Infobox-titel |
|---|---|---|
| `character` | Personages | Personage |
| `country` | Landen | Land |
| `region` | Regio's | Regio |
| `city` | Steden | Stad |
| `organization` | Organisaties | Organisatie |
| `deity` | Goden | God |
| `religion` | Religies | Religie |
| `item` | Voorwerpen | Voorwerp |
| `timeline_event` | één pagina "Tijdlijn" (lijst, op jaar gesorteerd) | Tijdlijn |

Opmerking: de `apiKey` in de frontend is een publieke Firebase-web-key (geen geheim; dat hoort zo bij Firebase). De import gebruikt een **service account** (Admin SDK), nooit een persoonlijk login.

Welke entiteitstypes uit welk document worden gehaald, staat in `config/sources.json` → `title_rules` (match op de bestandsnaam). Spreadsheets (zoals de tijdlijn) worden direct als CSV geparseerd naar `tijdlijn`.

## Twee routes

**Route A — zonder Google Cloud account (aanbevolen nu):** Drive-lezen gebeurt via de **Mistral google_drive-connector** (in deze sessie / in een Mistral Workflow met de connector eraan), niet via de Drive API. Jij hoeft dus géén Google Cloud project aan te maken. De import naar Firestore kan op twee manieren:

- **Via GitHub Actions (nadat de PR gemerged is naar main):** `.github/workflows/import-pages.yml` — handmatig starten via **Run workflow** (standaard dry-run). Gebruikt alleen de secrets `FIREBASE_PROJECT_ID` + `FIREBASE_SERVICE_ACCOUNT_JSON` en importeert `dry-run/pages.json` naar collectie `pages`.
- **Lokaal:** met het Firebase service account als bestand (zie onderstaand commando).

```bash
# 1. pages.json maken (hier in de sessie, via de Drive-connector) -> dry-run/pages.json
# 2. importeren naar Firestore (lokaal, alleen Firebase-creds nodig):
export FIREBASE_PROJECT_ID=the-lore-wiki
export FIREBASE_SERVICE_ACCOUNT_JSON="$(cat firebase-service-account.json)"
python -m lore_sync import dry-run/pages.json --dry-run   # check
python -m lore_sync import dry-run/pages.json             # echte import
```

Let op: `MISTRAL_API_KEY` is alleen voor LLM-calls (api.mistral.ai) — daar kun je **niet** Drive mee lezen. De Drive-toegang zit in de aparte google_drive-connector van de Mistral-sessie. Die connector is sessie-gebonden: een GitHub Actions-run kan daar niet bij.

**Route B — volledige sync in GitHub Actions (optioneel):** hiervoor is wél een Google Cloud project + service account nodig (zie hieronder). De workflow `.github/workflows/sync-lore.yml` draait wekelijks (zondag 03:00 UTC) en handmatig via **Run workflow** (standaard als dry run).

### Google Drive-toegang via service account (alleen Route B)

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

### 4. GitHub Actions (alleen Route B)

Zet in de repo onder **Settings → Secrets and variables → Actions** de secrets: `MISTRAL_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`. Secrets zijn write-only: ik kan ze niet uitlezen — voor Route A gebruik je het lokale key-bestand.

## Lokaal draaien

```bash
pip install -r requirements-dev.txt
export MISTRAL_API_KEY=...
export GOOGLE_SERVICE_ACCOUNT_JSON='$(cat service-account.json)'
export FIREBASE_PROJECT_ID=...
export FIREBASE_SERVICE_ACCOUNT_JSON='$(cat firebase-key.json)'

python -m lore_sync list                                  # toon Drive-bestanden
python -m lore_sync sync --dry-run --output pages.json    # extractie, zonder Firestore-writes
python -m lore_sync sync --types character timeline_event # alleen bepaalde types
python -m lore_sync sync --force                          # alles opnieuw
python -m lore_sync import dry-run/pages.json --dry-run   # import-preview (geen Google nodig)
python -m lore_sync import dry-run/pages.json             # importeer naar Firestore
pytest                                                    # tests
```

Zonder Firestore-credentials kun je met `--dry-run` (of `DRY_RUN=true`) de extractie testen; de Firestore-secrets zijn dan niet nodig.

## Extending

- Nieuwe bronmap: voeg het folder-ID toe aan `folders` in `config/sources.json` (of `--folders`).
- Nieuw documenttype: voeg een regel toe aan `title_rules` en een schema in `lore_sync/schemas.py`.
- Bestaand entiteitstype uitbreiden: pas het extractieschema in `lore_sync/schemas.py` én de infobox-rijen/content in `lore_sync/page_builder.py` aan; de categorie/caption staat in `config/sources.json` → `entity_pages`.
