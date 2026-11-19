import io
import json

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

FOLDER_MIME = "application/vnd.google-apps.folder"
DRAWING_MIME = "application/vnd.google-apps.drawing"
DRAWING_EXPORT_MIME = "image/png"
IMAGE_MIME_PREFIX = "image/"

EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/markdown",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}

FIELDS = "nextPageToken, files(id,name,mimeType,modifiedTime,size)"


def is_image_mime(mime) -> bool:
    return bool(mime) and mime.startswith(IMAGE_MIME_PREFIX)


def build_service(credentials_json: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(credentials_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _download(request) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def download_file_bytes(service, file_id: str) -> bytes:
    request = service.files().get(fileId=file_id, alt="media", supportsAllDrives=True)
    return _download(request)


def export_file_bytes(service, file_id: str, mime: str) -> bytes:
    request = service.files().export_media(fileId=file_id, mimeType=mime)
    return _download(request)


def iter_folder_files(service, folder_ids):
    seen = set()
    queue = list(folder_ids)
    while queue:
        folder_id = queue.pop(0)
        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                corpora="allDrives",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields=FIELDS,
                pageToken=page_token,
                pageSize=200,
            ).execute()
            for meta in resp.get("files", []):
                if meta["id"] in seen:
                    continue
                seen.add(meta["id"])
                if meta.get("mimeType") == FOLDER_MIME:
                    queue.append(meta["id"])
                    continue
                yield meta
            page_token = resp.get("nextPageToken")
            if not page_token:
                break


def export_file_text(service, meta) -> str:
    mime = meta.get("mimeType", "")
    if mime not in EXPORT_MIME:
        return ""
    return export_file_bytes(service, meta["id"], EXPORT_MIME[mime]).decode("utf-8", errors="replace")
