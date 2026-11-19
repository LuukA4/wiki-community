import argparse
import json
import logging
import sys

from .config import load_settings, validate
from .importer import import_images, import_pages, load_images_json, load_pages_json
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
    imp_img = sub.add_parser("import-images", help="Importeer een images.json naar de images-collectie (geen Google Drive nodig)")
    imp_img.add_argument("file", help="Pad naar images.json (naast de pages.json van een sync)")
    imp_img.add_argument("--dry-run", action="store_true", help="Alleen tonen wat er geschreven zou worden")
    imp_img.add_argument("--force", action="store_true", help="Overschrijf afbeeldingen die al bestaan")
    imp_img.add_argument("--config", help="Pad naar sources.json")
    ver = sub.add_parser("verify", help="Vergelijk Drive-bronnen met de pagina's (where did tekst/links verloren?)")
    ver.add_argument("--pages", help="Pad naar pages.json (standaard: lees uit Firestore)")
    ver.add_argument("--output", help="Schrijf het rapport als JSON naar dit pad")
    ver.add_argument("--config", help="Pad naar sources.json")
    ver.add_argument("--folders", nargs="*", help="Override Drive folder IDs")
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

    if args.command == "import-images":
        problems = validate(settings, need_drive=False, need_mistral=False, need_firestore=not settings.dry_run)
        if problems:
            for problem in problems:
                logging.error(problem)
            return 2
        images = load_images_json(args.file)
        from .firestore_sink import FirestoreSink

        sink = FirestoreSink(
            settings.firebase_project_id,
            settings.firebase_credentials_json,
            settings.dry_run,
            images_collection=settings.sources.get("images_collection", "images"),
        )
        result = import_images(images, sink, overwrite=settings.force)
        result["dry_run"] = settings.dry_run
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "verify":
        if args.pages:
            problems = validate(settings, need_drive=True, need_mistral=False, need_firestore=False)
            pages = load_pages_json(args.pages)
        else:
            problems = validate(settings, need_drive=True, need_mistral=False, need_firestore=True)
            pages = None
        if problems:
            for problem in problems:
                logging.error(problem)
            return 2
        from .firestore_sink import FirestoreSink
        from .verify import run_verify, save_report

        if pages is None:
            sink = FirestoreSink(
                settings.firebase_project_id,
                settings.firebase_credentials_json,
                settings.dry_run,
                pages_collection=settings.sources.get("pages_collection", "pages"),
            )
            pages = sink.list_pages()
        report = run_verify(settings, pages)
        if args.output:
            save_report(report, args.output)
            logging.info("Rapport weggeschreven naar %s", args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
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
