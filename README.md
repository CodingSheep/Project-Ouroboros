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

- **Python 3.13** with [Flask](https://flask.palletsprojects.com/)
- Vanilla JavaScript (no framework) for drag-sort, sequential playback, and loop logic
- JSON file for playlist persistence, local filesystem for audio storage
- Runs as a Docker container behind an nginx reverse proxy with Let's Encrypt HTTPS (This is not neccesary for personal setups. This is just what I use.)

## Project Structure

```
app.py                  # Flask routes, auth, playlist CRUD, file upload, audio serving
static/
  css/style.css         # Styling
  js/
    player.js           # Audio playback logic (play, pause, stop, next, volume)
    ui.js               # DOM/UI logic (drag-sort, file upload, auto-save)
    utils.js            # Shared utilities (formatTime, reorderArrayByDom)
  uploads/              # Audio files, organized by playlist name (gitignored)
templates/
  login.html            # Password login page
  playlists.html        # Playlist list view
  player.html           # Per-playlist player view
playlists.json          # Playlist state (gitignored — user data)
requirements.txt        # Python dependencies
```

## Running Locally

### Prerequisites

- Python 3.13+
- pip

### Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```
MUSIC_APP_PASSWORD=your-chosen-password
FLASK_SECRET_KEY=your-secret-key
```

Run:

```bash
python app.py
```

Navigate to `http://localhost:5000`.

## Deployment

Intended to run as a Docker container behind an nginx reverse proxy. See `Dockerfile` and `compose.yaml` for deployment configuration. Audio files and playlist state are persisted via volume mounts and are not included in this repository.

## Usage

1. Log in with your configured password
2. Create a playlist and give it a name
3. Drag audio files onto the dropzone or use the file picker to add tracks
4. Reorder tracks by dragging the `≡` handle
5. Toggle **Repeat On/Off** per track to control looping behavior
6. Press **Play** on the first track — playback chains automatically through the playlist
7. Changes save automatically; press **Save Playlist** for an explicit confirmation

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE) for details.