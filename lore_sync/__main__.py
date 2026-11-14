import argparse
import json
import logging
import sys

from .config import load_settings, validate
from .importer import import_pages, load_pages_json
from .pipeline import list_drive_files, run_sync


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="lore_sync",
        description="Synchroniseer lore-documenten uit Google Drive naar Firestore met AI-extractie.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="Voer een sync-run uit (Drive -> AI -> Firestore)")
    sync.add_argument("--dry-run", action="store_true", help="Geen writes naar Firestore, wel AI-extractie")
    sync.add_argument("--force", action="store_true", help="Negeer sync_state en overschrijf bestaande pagina's")
    sync.add_argument("--config", help="Pad naar sources.json")
    sync.add_argument("--folders", nargs="*", help="Override Drive folder IDs")
    sync.add_argument("--types", nargs="*", help="Beperk tot deze entiteitstypes")
    sync.add_argument("--output", help="Schrijf de resulterende pagina's als JSON naar dit pad")
    listing = sub.add_parser("list", help="Toon alle Drive-bestanden in de geconfigureerde mappen")
    listing.add_argument("--config", help="Pad naar sources.json")
    listing.add_argument("--folders", nargs="*", help="Override Drive folder IDs")
    imp = sub.add_parser("import", help="Importeer een pages.json naar Firestore (geen Google Drive nodig)")
    imp.add_argument("file", help="Pad naar pages.json (uit dry-run/ of --output van sync)")
    imp.add_argument("--dry-run", action="store_true", help="Alleen tonen wat er geschreven zou worden")
    imp.add_argument("--force", action="store_true", help="Overschrijf pagina's die al bestaan")
    imp.add_argument("--config", help="Pad naar sources.json")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = load_settings(
        sources_path=args.config,
        dry_run=getattr(args, "dry_run", False),
        force=getattr(args, "force", False),
        folders=getattr(args, "folders", None),
    )

    if args.command == "import":
        problems = validate(settings, need_drive=False, need_mistral=False, need_firestore=not settings.dry_run)
        if problems:
            for problem in problems:
                logging.error(problem)
            return 2
        pages = load_pages_json(args.file)
        from .firestore_sink import FirestoreSink

        sink = FirestoreSink(
            settings.firebase_project_id,
            settings.firebase_credentials_json,
            settings.dry_run,
            pages_collection=settings.sources.get("pages_collection", "pages"),
        )
        result = import_pages(pages, sink, overwrite=settings.force)
        result["dry_run"] = settings.dry_run
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    need_firestore = args.command == "sync" and not settings.dry_run
    problems = validate(settings, need_firestore=need_firestore)
    if problems:
        for problem in problems:
            logging.error(problem)
        return 2

    if args.command == "list":
        print(json.dumps(list_drive_files(settings), ensure_ascii=False, indent=2))
        return 0

    summary = run_sync(settings, only_types=args.types, output_path=args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
