# Project Ouroboros

A self-hosted web playlist manager for playing custom audio files during TTRPG sessions, built with Flask.

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

> **Rewrite in progress.** `main` is being rebuilt on Django (see Status below). The original Flask app lives on the [`archive/flask`](../../tree/archive/flask) branch and still runs in production until the new version replaces it.

- **Python 3.13** with [Django](https://www.djangoproject.com/) 6.1
- **SQLite** for folders, playlists and tracks; audio files stay on disk under generated names
- Django templates, [htmx](https://htmx.org/) and [SortableJS](https://sortablejs.github.io/Sortable/) for the UI (no JavaScript build step)
- gunicorn + whitenoise in production, behind nginx; nginx sends the audio files (`X-Accel-Redirect`) after Django checks the login

## Status

| Phase | |
|---|---|
| 1. Foundation: models (nested folders, playlists, tracks), admin, login, protected audio | ✅ |
| 2. Import from the Flask app's `playlists.json` + uploads | ⏳ |
| 3. Library page: folder tree, drag to reorder/move | ⏳ |
| 4. Player page | ⏳ |
| 5. Cutover to production | ⏳ |

## Development

```bash
cp .env.example .env            # then set DJANGO_SECRET_KEY
mkdir -p data
docker compose build music-next
docker compose run --rm music-next python manage.py migrate
docker compose run --rm music-next python manage.py createsuperuser
docker compose up -d music-next  # http://localhost:8001
docker compose run --rm music-next python manage.py test
```

Data lives in `data/` (`db.sqlite3`, `media/`), which is not in git.

## Project Structure

```
config/                 # Django project: settings (from environment), URLs
library/                # The app
  models.py             # Folder (nested via parent), Playlist, Track (+ file cleanup)
  admin.py              # Admin site for folders, playlists and tracks
  views.py              # Library page, login-protected audio (X-Accel-Redirect)
  templates/library/    # Library templates
  static/library/       # CSS (and later htmx, SortableJS, player JS)
  tests.py
templates/              # base.html, login page
data/                   # db.sqlite3 + media/ (gitignored)
compose.yaml            # music-next (Django, dev) + music-player (old Flask app until cutover)
```

## Deployment

Runs as a Docker container behind an nginx reverse proxy (gunicorn, whitenoise for CSS/JS). `data/` is mounted as a volume and isn't in this repository. Production settings come from environment variables: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `MEDIA_ACCEL_PREFIX` for nginx to serve audio.

## Usage

*(Describes the Flask app; updated as the rewrite reaches each feature.)*


1. Log in with your configured password
2. Create a playlist and give it a name
3. Drag audio files onto the dropzone or use the file picker to add tracks
4. Reorder tracks by dragging the `≡` handle
5. Toggle **Repeat On/Off** per track to control looping behavior
6. Press **Play** on the first track — playback chains automatically through the playlist
7. Changes save automatically; press **Save Playlist** for an explicit confirmation

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE) for details.