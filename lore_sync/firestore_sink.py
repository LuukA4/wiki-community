import json
from datetime import datetime, timezone

from .merge import slugify, entity_key
from .schemas import name_field


def _now():
    return datetime.now(timezone.utc).isoformat()


class FirestoreSink:
    def __init__(self, project_id: str, credentials_json: str, dry_run: bool = False):
        self.dry_run = dry_run
        self.db = None
        if not dry_run:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(json.loads(credentials_json))
                firebase_admin.initialize_app(cred, {"projectId": project_id})
            self.db = firestore.client()

    def write_entities(self, collection: str, entities: list) -> int:
        if not entities:
            return 0
        if self.dry_run:
            return len(entities)
        written = 0
        batch = self.db.batch()
        pending = 0
        for item in entities:
            doc_id = item.get("id") or slugify(item.get(name_field(item.get("type", "")), ""))
            data = dict(item)
            data["id"] = doc_id
            data["updatedAt"] = _now()
            batch.set(self.db.collection(collection).document(doc_id), data, merge=True)
            pending += 1
            if pending == 500:
                batch.commit()
                written += pending
                batch = self.db.batch()
                pending = 0
        if pending:
            batch.commit()
            written += pending
        return written

    def get_state(self, file_id: str):
        if self.dry_run:
            return None
        doc = self.db.collection("sync_state").document(file_id).get()
        return doc.to_dict() if doc.exists else None

    def set_state(self, file_id: str, meta: dict, stats: dict) -> None:
        if self.dry_run:
            return
        self.db.collection("sync_state").document(file_id).set(
            {
                "fileId": file_id,
                "name": meta.get("name"),
                "mimeType": meta.get("mimeType"),
                "modifiedTime": meta.get("modifiedTime"),
                "processedAt": _now(),
                "stats": stats,
            },
            merge=True,
        )

    def write_run_summary(self, summary: list) -> None:
        if self.dry_run:
            return
        self.db.collection("sync_runs").document().set({"startedAt": _now(), "files": summary})
