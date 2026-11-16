import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES_PATH = REPO_ROOT / "config" / "sources.json"

SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"


@dataclass
class Settings:
    drive_folder_ids: list
    mistral_api_key: str
    mistral_model: str
    google_credentials_json: str
    firebase_project_id: str
    firebase_credentials_json: str
    sources_path: Path
    sources: dict = field(default_factory=dict)
    dry_run: bool = False
    force: bool = False
    chunk_size: int = 60000
    chunk_overlap: int = 1
    request_pause: float = 0.5


def _bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_sources(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_settings(sources_path=None, dry_run=False, force=False, folders=None) -> Settings:
    path = Path(sources_path) if sources_path else DEFAULT_SOURCES_PATH
    sources = load_sources(path)
    folder_ids = folders or sources.get("folders") or [os.environ.get("DRIVE_ROOT_FOLDER_ID", "")]
    return Settings(
        drive_folder_ids=[f for f in folder_ids if f],
        mistral_api_key=os.environ.get("MISTRAL_API_KEY", ""),
        mistral_model=os.environ.get("MISTRAL_MODEL", "mistral-large-latest"),
        google_credentials_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        firebase_project_id=os.environ.get("FIREBASE_PROJECT_ID", ""),
        firebase_credentials_json=os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", ""),
        sources_path=path,
        sources=sources,
        dry_run=dry_run or _bool(os.environ.get("DRY_RUN", "false")),
        force=force or _bool(os.environ.get("FORCE", "false")),
        chunk_size=int(os.environ.get("CHUNK_SIZE", "60000")),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", "1")),
        request_pause=float(os.environ.get("REQUEST_PAUSE", "0.5")),
    )


def validate(settings: Settings, need_drive: bool = True, need_mistral: bool = True, need_firestore: bool = True) -> list:
    problems = []
    if need_drive:
        if not settings.drive_folder_ids:
            problems.append("Geen Drive folder IDs: zet 'folders' in config/sources.json of DRIVE_ROOT_FOLDER_ID.")
        if not settings.google_credentials_json:
            problems.append("GOOGLE_SERVICE_ACCOUNT_JSON ontbreekt (service account JSON met Drive read-toegang).")
    if need_mistral and not settings.mistral_api_key:
        problems.append("MISTRAL_API_KEY ontbreekt.")
    if need_firestore:
        if not settings.firebase_project_id:
            problems.append("FIREBASE_PROJECT_ID ontbreekt.")
        if not settings.firebase_credentials_json:
            problems.append("FIREBASE_SERVICE_ACCOUNT_JSON ontbreekt (service account met Firestore rechten).")
        else:
            try:
                json.loads(settings.firebase_credentials_json)
            except ValueError:
                problems.append(
                    "FIREBASE_SERVICE_ACCOUNT_JSON is geen geldige JSON (moet beginnen met '{'): "
                    "plak de volledige inhoud van het service-account-keybestand, geen bestandsnaam of placeholder."
                )
    return problems
