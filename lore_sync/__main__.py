import argparse
import json
import logging
import sys

from .config import load_settings, validate
from .pipeline import list_drive_files, run_sync


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="lore_sync",
        description="Synchroniseer lore-documenten uit Google Drive naar Firestore met AI-extractie.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="Voer een sync-run uit")
    sync.add_argument("--dry-run", action="store_true", help="Geen writes naar Firestore, wel AI-extractie")
    sync.add_argument("--force", action="store_true", help="Negeer sync_state en verwerk alles opnieuw")
    sync.add_argument("--config", help="Pad naar sources.json")
    sync.add_argument("--folders", nargs="*", help="Override Drive folder IDs")
    sync.add_argument("--types", nargs="*", help="Beperk tot deze entiteitstypes")
    listing = sub.add_parser("list", help="Toon alle Drive-bestanden in de geconfigureerde mappen")
    listing.add_argument("--config", help="Pad naar sources.json")
    listing.add_argument("--folders", nargs="*", help="Override Drive folder IDs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = load_settings(
        sources_path=args.config,
        dry_run=getattr(args, "dry_run", False),
        force=getattr(args, "force", False),
        folders=args.folders,
    )
    need_firestore = args.command == "sync" and not settings.dry_run
    problems = validate(settings, need_firestore)
    if problems:
        for problem in problems:
            logging.error(problem)
        return 2

    if args.command == "list":
        print(json.dumps(list_drive_files(settings), ensure_ascii=False, indent=2))
        return 0

    summary = run_sync(settings, only_types=args.types)
    print(json.dumps({"dry_run": settings.dry_run, "files": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
