import json

from lore_sync.config import Settings, validate


def _settings(**overrides):
    base = dict(
        drive_folder_ids=[],
        mistral_api_key="",
        mistral_model="mistral-large-latest",
        google_credentials_json="",
        firebase_project_id="",
        firebase_credentials_json="",
        sources_path="config/sources.json",
    )
    base.update(overrides)
    return Settings(**base)


def test_validate_firestore_rejects_non_json_credentials():
    s = _settings(firebase_project_id="the-lore-wiki", firebase_credentials_json="firebase-key.json")
    problems = validate(s, need_drive=False, need_mistral=False, need_firestore=True)
    assert any("FIREBASE_SERVICE_ACCOUNT_JSON" in p for p in problems)


def test_validate_firestore_accepts_valid_service_account_json():
    s = _settings(
        firebase_project_id="the-lore-wiki",
        firebase_credentials_json=json.dumps({"type": "service_account", "project_id": "the-lore-wiki"}),
    )
    assert validate(s, need_drive=False, need_mistral=False, need_firestore=True) == []


def test_validate_firestore_flags_missing_values():
    problems = validate(_settings(), need_drive=False, need_mistral=False, need_firestore=True)
    assert any("FIREBASE_PROJECT_ID" in p for p in problems)
    assert any("FIREBASE_SERVICE_ACCOUNT_JSON" in p for p in problems)
