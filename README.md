# Project Ouroboros

A self-hosted web playlist manager for playing custom audio files during TTRPG sessions, built with Django.

Kenku FM's built-in playlists and soundboards lack the flexibility I need for more dynamic and adaptive music during combat encounters. Project Ouroboros fills that gap — allowing audio files to play in sequence with per-track loop control, simulating the kind of phase-transitioning music you'd hear in a video game boss fight.

## Features

- **Playlist management** — create, rename, delete, and reorder playlists
- **Track management** — drag and drop audio files (MP3) into a playlist, reorder via drag handle, remove individually
- **Per-track loop control** — toggle "Repeat On/Off" per track, checked at the end of playback so it can be changed on the fly
- **Sequential playback** — when a track ends on "Repeat Off", the next track plays automatically
- **Volume control** — global volume slider, persisted per playlist
- **Auto-save** — playlist state (order, loop settings, volume) saves automatically on any change
- **Password-protected** — simple login wall, intended for personal/trusted use

## How It Works

Tracks play in sequence. When a track ends:
- **Repeat On** → the track loops immediately with no delay
- **Repeat Off** → the next track in the playlist starts automatically

This allows pre-edited audio files (e.g. fight intro → fight loop → fight end) to chain together seamlessly, emulating adaptive audio from video games without needing a full middleware solution.

## Tech Stack

> `main` is the Django rewrite. The original Flask app is on the [`archive/flask`](../../tree/archive/flask) branch.

- **Python 3.13** with [Django](https://www.djangoproject.com/) 6.1
- **SQLite** for folders, playlists and tracks; audio files stay on disk under generated names
- Django templates, [htmx](https://htmx.org/) and [SortableJS](https://sortablejs.github.io/Sortable/) for the UI (no JavaScript build step)
- gunicorn + whitenoise in production, behind nginx; nginx sends the audio files (`X-Accel-Redirect`) after Django checks the login

## Status

| Phase | |
|---|---|
| 1. Foundation: models (nested folders, playlists, tracks), admin, login, protected audio | ✅ |
| 2. Import from the Flask app's `playlists.json` + uploads | ✅ |
| 3. Library page: folder tree, create/rename/delete, drag to reorder/move | ✅ |
| 4. Player page: playback, Repeat, volume, uploads, all saved as you go | ✅ |
| 5. Cutover to production | ✅ |

## Development

```bash
cp .env.example .env                                   # then set DJANGO_SECRET_KEY
docker compose --profile dev up -d --build music-dev   # http://localhost:8001, data in dev-data/
docker compose run --rm music-dev python manage.py createsuperuser
docker compose run --rm music-dev python manage.py test
docker compose run --rm music-dev python manage.py import_flask          # show what the import would do
docker compose run --rm music-dev python manage.py import_flask --apply  # import playlists.json + static/uploads
```

The dev container mounts the code (edits apply without a rebuild) and keeps its own data in `dev-data/`.

The import turns "Campaign - Playlist" names into a Campaign folder, copies the audio (originals untouched), and skips playlists already imported, so it's safe to run again.

The live app's data lives in `data/` (`db.sqlite3`, `media/`), which is not in git.

## Project Structure

```
config/                 # Django project: settings (from environment), URLs
library/                # The app
  models.py             # Folder (nested via parent), Playlist, Track (+ file cleanup)
  admin.py              # Admin site for folders, playlists and tracks
  management/commands/import_flask.py  # One-time import from the Flask app
  views.py              # Library page, player endpoints, login-protected audio (with seeking)
  templates/library/    # Library templates
  static/library/       # CSS, library.js (drag/drop, forms), player.js, vendor/ (htmx 2.0.11, SortableJS 1.15.7)
  tests.py
templates/              # base.html, login page
data/                   # db.sqlite3 + media/ (gitignored)
compose.yaml            # music-player (live, gunicorn) + music-dev (development, profile "dev")
```

## Deployment

`docker compose up -d --build music-player` runs gunicorn on port 8000 (migrations are applied on start; whitenoise serves CSS/JS) behind an nginx reverse proxy. `data/` is mounted as a volume and isn't in this repository. Settings come from environment variables: `DJANGO_SECRET_KEY` (in `.env`), and in `compose.yaml` `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and `MEDIA_ACCEL_PREFIX`.

Audio is never served without a login: Django checks it, then answers with `X-Accel-Redirect: /protected-media/<file>`, and nginx sends the file from an `internal` location:

```nginx
location /protected-media/ {
    internal;
    alias /music-media/;   # data/media, mounted read-only into nginx
}
```

Back up `data/media` plus a copy of `db.sqlite3` made with SQLite's backup API (for example `sqlite3 data/db.sqlite3 ".backup copy.sqlite3"`); copying the live file while the app runs can give a broken copy.

## Usage

1. Log in with your Django account (`createsuperuser`, see Development)
2. On the library page, make folders (**+ Folder**, or **+ Folder** on a folder for a subfolder) and playlists; drag the `≡` handle to reorder or move them
3. Open a playlist and drop audio files onto the page (or **Browse files**); each uploads once, straight away
4. Reorder tracks by dragging `≡`, and toggle **Repeat On/Off** per track
5. Press **Play** on the first track; playback chains through the playlist, and a track with Repeat On loops until you turn it off
6. Everything (order, Repeat, volume, removals) saves as you go; there is no Save button

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE) for details.