"""Import the old Flask app's playlists.json and uploaded audio.

Shows what it would do by default; pass --apply to write. Safe to run again:
playlists that already exist (same name in the same folder) are skipped.

"Campaign - Playlist" names become a "Campaign" folder holding "Playlist".
Audio is copied (the old files are left alone), so the old app keeps working.
"""
import json
from pathlib import Path
from urllib.parse import unquote

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from library.models import Folder, Playlist, Track

URL_PREFIX = "/static/uploads/"


def split_name(name: str) -> tuple[str | None, str]:
    """'Adrift in Time - Taifu Clan' -> ('Adrift in Time', 'Taifu Clan')."""
    folder, sep, rest = name.partition(" - ")
    if sep and folder.strip() and rest.strip():
        return folder.strip(), rest.strip()
    return None, name.strip()


def resolve(uploads: Path, url: str) -> Path:
    """Track URL -> file under the uploads folder. Raises CommandError if it
    points elsewhere or the file is missing."""
    path = unquote(url)
    if not path.startswith(URL_PREFIX):
        raise CommandError(f"Unexpected track URL: {url}")
    target = (uploads / path[len(URL_PREFIX):]).resolve()
    if uploads not in target.parents:
        raise CommandError(f"Track URL points outside the uploads folder: {url}")
    if not target.is_file():
        raise CommandError(f"Missing file for {url}")
    return target


class Command(BaseCommand):
    help = "Import playlists.json and static/uploads from the old Flask app."

    def add_arguments(self, parser):
        parser.add_argument("--json", default="playlists.json", help="Path to playlists.json")
        parser.add_argument("--uploads", default="static/uploads", help="Path to the uploads folder")
        parser.add_argument("--apply", action="store_true", help="Write to the database (default: only show)")

    def handle(self, *args, **opts):
        json_path = Path(opts["json"])
        uploads = Path(opts["uploads"]).resolve()
        if not json_path.is_file():
            raise CommandError(f"Not found: {json_path}")
        if not uploads.is_dir():
            raise CommandError(f"Not found: {uploads}")
        data = json.loads(json_path.read_text())
        if not isinstance(data, dict):
            raise CommandError("Expected playlists.json to be an object of {name: playlist}.")

        # Check everything before writing anything.
        plan = []
        for full_name, pl in data.items():
            folder_name, name = split_name(full_name)
            tracks = [(t["name"], bool(t.get("loop", False)), resolve(uploads, t["url"]))
                      for t in pl.get("tracks", [])]
            plan.append((folder_name, name, float(pl.get("volume", 1.0)), tracks))

        apply = opts["apply"]
        copied: list[Track] = []
        counts = {"folders": 0, "playlists": 0, "tracks": 0, "skipped": 0}
        try:
            with transaction.atomic():
                folders: dict[str, Folder] = {}
                for folder_name, name, volume, tracks in plan:
                    folder = None
                    if folder_name:
                        folder = folders.get(folder_name)
                        if folder is None:
                            folder = Folder.objects.filter(name=folder_name, parent=None).first()
                            if folder is None:
                                counts["folders"] += 1
                                self.stdout.write(f"+ folder   {folder_name}")
                                folder = Folder(name=folder_name)
                                if apply:
                                    folder.save()
                            folders[folder_name] = folder
                    label = f"{folder_name} / {name}" if folder_name else name
                    if folder is None:
                        exists = Playlist.objects.filter(folder=None, name=name).exists()
                    else:   # a folder not saved yet (dry run) can't hold anything
                        exists = folder.pk is not None and folder.playlists.filter(name=name).exists()
                    if exists:
                        counts["skipped"] += 1
                        self.stdout.write(f"= skip     {label} (already imported)")
                        continue
                    counts["playlists"] += 1
                    counts["tracks"] += len(tracks)
                    self.stdout.write(f"+ playlist {label} ({len(tracks)} tracks, volume {volume:g})")
                    if not apply:
                        continue
                    playlist = Playlist.objects.create(name=name, folder=folder, volume=volume)
                    for track_name, loop, src in tracks:
                        track = Track(playlist=playlist, name=track_name, loop=loop)
                        with src.open("rb") as f:
                            track.file.save(src.name, File(f), save=False)
                        copied.append(track)
                        track.save()
        except BaseException:
            # The database rolled back; remove the files copied so far.
            for track in copied:
                track.file.delete(save=False)
            raise

        summary = (f"{counts['folders']} folders, {counts['playlists']} playlists, "
                   f"{counts['tracks']} tracks; {counts['skipped']} already imported.")
        if apply:
            self.stdout.write(self.style.SUCCESS(f"Imported {summary}"))
        else:
            self.stdout.write(self.style.WARNING(f"Would import {summary} Nothing written; run with --apply."))
