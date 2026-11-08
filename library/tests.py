import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Folder, Playlist, Track


class TempMediaMixin:
    """Each test gets its own empty MEDIA_ROOT."""

    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def make_track(self, playlist, name="Boss Loop.mp3", loop=False):
        return Track.objects.create(playlist=playlist, name=name, loop=loop,
                                    file=SimpleUploadedFile(name, b"ID3fake-audio"))


class FolderTests(TestCase):
    def test_new_items_go_to_the_end_among_siblings(self):
        a = Folder.objects.create(name="Adrift in Time")
        b = Folder.objects.create(name="Project 1313")
        arc = Folder.objects.create(name="Arc 1", parent=a)
        self.assertEqual((a.position, b.position), (0, 1))
        self.assertEqual(arc.position, 0)   # first inside its own parent

    def test_path_shows_the_full_nesting(self):
        a = Folder.objects.create(name="Campaign")
        arc = Folder.objects.create(name="Arc", parent=a)
        self.assertEqual(arc.path(), "Campaign / Arc")

    def test_folder_cannot_go_inside_itself_or_a_subfolder(self):
        a = Folder.objects.create(name="Campaign")
        arc = Folder.objects.create(name="Arc", parent=a)
        a.parent = a
        with self.assertRaises(ValidationError):
            a.full_clean()
        a.parent = arc
        with self.assertRaises(ValidationError):
            a.full_clean()


class TrackFileTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.folder = Folder.objects.create(name="Campaign")
        self.playlist = Playlist.objects.create(name="Boss", folder=self.folder)

    def test_files_get_generated_names_and_keep_the_display_name(self):
        t = self.make_track(self.playlist, name="Taifu Boss Loop.MP3")
        self.assertRegex(t.file.name, r"^tracks/[0-9a-f]{32}\.mp3$")
        self.assertEqual(t.name, "Taifu Boss Loop.MP3")

    def test_deleting_a_track_deletes_its_file(self):
        t = self.make_track(self.playlist)
        path = Path(t.file.path)
        self.assertTrue(path.exists())
        t.delete()
        self.assertFalse(path.exists())

    def test_deleting_a_folder_deletes_files_of_everything_inside(self):
        arc = Folder.objects.create(name="Arc", parent=self.folder)
        inner = Playlist.objects.create(name="Inner", folder=arc)
        paths = [Path(self.make_track(p).file.path) for p in (self.playlist, inner)]
        self.folder.delete()
        self.assertFalse(any(p.exists() for p in paths))
        self.assertFalse(Track.objects.exists())

    def test_renaming_or_moving_a_playlist_does_not_touch_files(self):
        t = self.make_track(self.playlist)
        before = t.file.name
        other = Folder.objects.create(name="Other")
        self.playlist.name = "Renamed"
        self.playlist.folder = other
        self.playlist.save()
        t.refresh_from_db()
        self.assertEqual(t.file.name, before)
        self.assertTrue(Path(t.file.path).exists())


class ViewTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user("gm", password="a-long-test-password")
        a = Folder.objects.create(name="Adrift in Time")
        arc = Folder.objects.create(name="Arc 1", parent=a)
        self.playlist = Playlist.objects.create(name="Taifu Clan", folder=arc)
        Playlist.objects.create(name="Loose Playlist")
        self.track = self.make_track(self.playlist)

    def test_pages_and_audio_require_login(self):
        for url in (reverse("library:home"), reverse("media", args=[self.track.file.name])):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn(reverse("login"), resp["Location"])

    def test_login_then_home_shows_the_nested_tree(self):
        resp = self.client.post(reverse("login"), {"username": "gm", "password": "a-long-test-password"})
        self.assertRedirects(resp, reverse("library:home"))
        html = self.client.get(reverse("library:home")).content.decode()
        for text in ("Adrift in Time", "Arc 1", "Taifu Clan", "Loose Playlist", "1 tracks"):
            self.assertIn(text, html)
        self.assertLess(html.index("Adrift in Time"), html.index("Arc 1"))
        self.assertLess(html.index("Arc 1"), html.index("Taifu Clan"))

    def test_audio_is_sent_to_logged_in_users(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("media", args=[self.track.file.name]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), b"ID3fake-audio")
        self.assertEqual(resp["Content-Type"], "audio/mpeg")

    @override_settings(MEDIA_ACCEL_PREFIX="/protected-media/")
    def test_audio_is_handed_to_nginx_when_configured(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("media", args=[self.track.file.name]))
        self.assertEqual(resp["X-Accel-Redirect"], "/protected-media/" + self.track.file.name)
        self.assertEqual(resp.content, b"")

    def test_paths_outside_media_are_refused(self):
        self.client.force_login(self.user)
        for path in ("../db.sqlite3", "tracks/../../etc/passwd", "tracks/missing.mp3"):
            self.assertEqual(self.client.get("/media/" + path).status_code, 404, path)


class ImportFlaskTests(TempMediaMixin, TestCase):
    """The import command, on a small copy of the old app's layout."""

    def setUp(self):
        super().setUp()
        self.src = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.src, ignore_errors=True)
        uploads = self.src / "uploads"
        (uploads / "Taifu Clan").mkdir(parents=True)
        (uploads / "Taifu Clan" / "Taifu Intro.mp3").write_bytes(b"intro")
        (uploads / "Taifu Clan" / "Taifu Loop.mp3").write_bytes(b"loop")
        (uploads / "Odd & Ends").mkdir()
        (uploads / "Odd & Ends" / "Rain #1.mp3").write_bytes(b"rain")
        (uploads / "Orphan").mkdir()
        (uploads / "Orphan" / "unused.mp3").write_bytes(b"x")
        self.uploads = uploads
        self.write_json({
            "Adrift in Time - Taifu Clan": {"volume": 0.55, "tracks": [
                {"name": "Taifu Intro.mp3", "loop": False, "url": "/static/uploads/Taifu Clan/Taifu Intro.mp3"},
                {"name": "Taifu Loop.mp3", "loop": True, "url": "/static/uploads/Taifu%20Clan/Taifu%20Loop.mp3"},
            ]},
            "Adrift in Time - Second": {"volume": 1.0, "tracks": []},
            "Ambience": {"volume": 1.0, "tracks": [
                {"name": "Rain #1.mp3", "loop": True, "url": "/static/uploads/Odd & Ends/Rain #1.mp3"},
            ]},
        })

    def write_json(self, data):
        import json
        (self.src / "playlists.json").write_text(json.dumps(data))

    def run_import(self, *extra):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("import_flask", "--json", str(self.src / "playlists.json"),
                     "--uploads", str(self.uploads), *extra, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        out = self.run_import()
        self.assertIn("Would import 1 folders, 3 playlists, 3 tracks", out)
        self.assertFalse(Folder.objects.exists() or Playlist.objects.exists() or Track.objects.exists())
        self.assertFalse(any(Path(self.media_root).rglob("*.mp3")))

    def test_apply_builds_folders_playlists_and_tracks_in_order(self):
        self.run_import("--apply")
        campaign = Folder.objects.get()
        self.assertEqual((campaign.name, campaign.parent), ("Adrift in Time", None))
        self.assertEqual([p.name for p in campaign.playlists.all()], ["Taifu Clan", "Second"])
        taifu = campaign.playlists.get(name="Taifu Clan")
        self.assertEqual(taifu.volume, 0.55)
        self.assertEqual([(t.name, t.loop) for t in taifu.tracks.all()],
                         [("Taifu Intro.mp3", False), ("Taifu Loop.mp3", True)])
        self.assertEqual(taifu.tracks.first().file.read(), b"intro")
        loose = Playlist.objects.get(folder=None)
        self.assertEqual(loose.name, "Ambience")
        self.assertEqual(loose.tracks.get().file.read(), b"rain")

    def test_files_are_copied_and_originals_kept(self):
        self.run_import("--apply")
        self.assertTrue((self.uploads / "Taifu Clan" / "Taifu Intro.mp3").exists())
        self.assertEqual(len(list(Path(self.media_root).rglob("*.mp3"))), 3)   # orphan not copied

    def test_running_again_skips_what_is_already_there(self):
        self.run_import("--apply")
        out = self.run_import("--apply")
        self.assertIn("0 folders, 0 playlists, 0 tracks; 3 already imported", out)
        self.assertEqual(Folder.objects.count(), 1)
        self.assertEqual(Track.objects.count(), 3)

    def test_a_missing_file_stops_the_import_before_anything_is_written(self):
        from django.core.management.base import CommandError
        (self.uploads / "Odd & Ends" / "Rain #1.mp3").unlink()
        with self.assertRaises(CommandError):
            self.run_import("--apply")
        self.assertFalse(Playlist.objects.exists())
        self.assertFalse(any(Path(self.media_root).rglob("*.mp3")))

    def test_urls_outside_the_uploads_folder_are_refused(self):
        from django.core.management.base import CommandError
        (self.src / "secret.mp3").write_bytes(b"no")
        self.write_json({"X": {"volume": 1, "tracks": [
            {"name": "s", "loop": False, "url": "/static/uploads/../secret.mp3"}]}})
        with self.assertRaises(CommandError):
            self.run_import("--apply")
        self.assertFalse(Playlist.objects.exists())
