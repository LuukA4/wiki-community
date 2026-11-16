import json
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


class FirestoreSink:
    def __init__(self, project_id: str, credentials_json: str, dry_run: bool = False, pages_collection: str = "pages"):
        self.dry_run = dry_run
        self.pages_collection = pages_collection
        self.db = None
        if not dry_run:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(json.loads(credentials_json))
                firebase_admin.initialize_app(cred, {"projectId": project_id})
            self.db = firestore.client()
            self._server_timestamp = firestore.SERVER_TIMESTAMP

    def page_exists(self, doc_id: str) -> bool:
        if self.dry_run:
            return False
        return self.db.collection(self.pages_collection).document(doc_id).get().exists

    def write_page(self, page: dict, overwrite: bool = False) -> str:
        doc_id = page["docId"]
        if not overwrite and self.page_exists(doc_id):
            return "skipped"
        if self.dry_run:
            return "written"
        data = {
            "title": page["title"],
            "category": page.get("category", ""),
            "content": page.get("content", ""),
            "infoboxRows": page.get("infoboxRows", []),
            "infoboxCaption": page.get("infoboxCaption", ""),
            "updatedAt": self._server_timestamp,
        }
        self.db.collection(self.pages_collection).document(doc_id).set(data)
        return "written"

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
        self.db.collection("sync_runs").document().set({"finishedAt": _now(), "files": summary})
