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
        for text in ("Adrift in Time", "Arc 1", "Taifu Clan", "Loose Playlist", "1 track"):
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


class LibraryEditTests(TempMediaMixin, TestCase):
    """Create, rename, delete and move from the library page."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user("gm", password="a-long-test-password")
        self.client.force_login(self.user)
        self.campaign = Folder.objects.create(name="Campaign")
        self.arc = Folder.objects.create(name="Arc", parent=self.campaign)
        self.a = Playlist.objects.create(name="A", folder=self.campaign)
        self.b = Playlist.objects.create(name="B", folder=self.campaign)

    def post(self, view, *args, **data):
        return self.client.post(reverse(f"library:{view}", args=args), data)

    def test_everything_needs_login(self):
        self.client.logout()
        urls = [reverse("library:tree"), reverse("library:move"),
                reverse("library:create", args=["folder"]),
                reverse("library:rename", args=["folder", self.arc.pk]),
                reverse("library:delete", args=["folder", self.arc.pk])]
        for url in urls:
            self.assertEqual(self.client.post(url).status_code, 302, url)
        self.assertTrue(Folder.objects.filter(pk=self.arc.pk).exists())

    def test_create_folder_subfolder_and_playlist(self):
        self.post("create", "folder", name="  New Campaign  ")
        self.post("create", "folder", name="Arc 2", parent=self.campaign.pk)
        resp = self.post("create", "playlist", name="Boss", parent=self.arc.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Folder.objects.filter(name="New Campaign", parent=None).exists())
        self.assertEqual([f.name for f in self.campaign.children.all()], ["Arc", "Arc 2"])
        self.assertTrue(self.arc.playlists.filter(name="Boss").exists())
        self.assertContains(resp, "Boss")   # the refreshed tree comes back

    def test_form_is_served_and_blank_names_are_refused(self):
        resp = self.client.get(reverse("library:create", args=["playlist"]), {"parent": self.arc.pk})
        self.assertContains(resp, 'name="parent" value="%d"' % self.arc.pk)
        resp = self.post("create", "folder", name="   ")
        self.assertContains(resp, "Enter a name.")
        self.assertEqual(resp["HX-Retarget"], "#name-form")
        self.assertEqual(Folder.objects.count(), 2)

    def test_rename(self):
        self.post("rename", "folder", self.arc.pk, name="Arc One")
        self.post("rename", "playlist", self.a.pk, name="Alpha")
        self.arc.refresh_from_db(); self.a.refresh_from_db()
        self.assertEqual((self.arc.name, self.a.name), ("Arc One", "Alpha"))

    def test_unknown_kind_is_404_and_get_cannot_delete(self):
        self.assertEqual(self.post("create", "track", name="x").status_code, 404)
        self.assertEqual(self.client.get(reverse("library:delete", args=["folder", self.arc.pk])).status_code, 405)

    def test_delete_folder_removes_everything_inside_with_files(self):
        inner = Playlist.objects.create(name="Inner", folder=self.arc)
        path = Path(self.make_track(inner).file.path)
        self.post("delete", "folder", self.campaign.pk)
        self.assertFalse(Folder.objects.exists() or Playlist.objects.exists())
        self.assertFalse(path.exists())

    def test_delete_warning_counts_everything_inside(self):
        inner = Playlist.objects.create(name="Inner", folder=self.arc)
        self.make_track(inner); self.make_track(self.a)
        html = self.client.get(reverse("library:home")).content.decode()
        self.assertIn("3 playlists and 2 tracks", html)

    def test_reorder_playlists_within_a_folder(self):
        self.post("move", kind="playlist", id=self.b.pk, parent=self.campaign.pk, order=f"{self.b.pk},{self.a.pk}")
        self.assertEqual([p.name for p in self.campaign.playlists.all()], ["B", "A"])

    def test_move_playlist_into_another_folder_at_a_position(self):
        c = Playlist.objects.create(name="C", folder=self.arc)
        self.post("move", kind="playlist", id=self.a.pk, parent=self.arc.pk, order=f"{self.a.pk},{c.pk}")
        self.assertEqual([p.name for p in self.arc.playlists.all()], ["A", "C"])
        self.assertEqual([p.name for p in self.campaign.playlists.all()], ["B"])

    def test_move_to_top_level_and_folder_into_folder(self):
        self.post("move", kind="playlist", id=self.a.pk, parent="", order=str(self.a.pk))
        self.a.refresh_from_db()
        self.assertIsNone(self.a.folder)
        other = Folder.objects.create(name="Other")
        self.post("move", kind="folder", id=other.pk, parent=self.arc.pk, order=str(other.pk))
        self.assertEqual(other.__class__.objects.get(pk=other.pk).path(), "Campaign / Arc / Other")

    def test_folder_cannot_be_moved_into_its_own_subfolder(self):
        resp = self.post("move", kind="folder", id=self.campaign.pk, parent=self.arc.pk, order=str(self.campaign.pk))
        self.assertEqual(resp.status_code, 400)
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.parent)

    def test_page_loads_the_scripts(self):
        html = self.client.get(reverse("library:home")).content.decode()
        for name in ("htmx.min.js", "Sortable.min.js", "library.js", "X-CSRFToken"):
            self.assertIn(name, html)
