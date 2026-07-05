import json
import os
import secrets

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, send_from_directory, session
)
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
APP_PASSWORD = os.getenv("MUSIC_APP_PASSWORD")

PLAYLIST_FILE = 'playlists.json'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def load_playlists():
    if not os.path.exists(PLAYLIST_FILE):
        return {}
    with open(PLAYLIST_FILE, 'r') as f:
        raw = json.load(f)

    # Migrate old format: name -> [track, ...]  =>  name -> {"volume": 1.0, "tracks": [...]}
    migrated = {}
    changed = False
    for name, value in raw.items():
        if isinstance(value, list):
            migrated[name] = {"volume": 1.0, "tracks": value}
            changed = True
        else:
            migrated[name] = value
    if changed:
        save_playlists(migrated)
    return migrated


def save_playlists(data):
    with open(PLAYLIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# ----------------- Auth --------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if not APP_PASSWORD:
            error = "Server misconfigured: MUSIC_APP_PASSWORD not set."
        elif request.form.get('password') == APP_PASSWORD:
            session['authed'] = True
            session.permanent = True
            return redirect(request.args.get('next') or url_for('playlists'))
        else:
            error = "Incorrect password."
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ----------------- Playlist Management --------------------
@app.route('/')
@login_required
def playlists():
    data = load_playlists()
    return render_template('playlists.html', playlists=data)


@app.route('/playlist/add', methods=['POST'])
@login_required
def add_playlist():
    name = request.form['name']
    data = load_playlists()
    if name in data:
        return jsonify({"error": "Playlist already exists"}), 400
    data[name] = {"volume": 1.0, "tracks": []}
    save_playlists(data)
    return redirect(url_for('playlists'))


@app.route('/playlist/delete/<name>', methods=['POST'])
@login_required
def delete_playlist(name):
    data = load_playlists()
    if name in data:
        data.pop(name)
        save_playlists(data)
    return redirect(url_for('playlists'))


@app.route('/playlist/rename/<old_name>', methods=['POST'])
@login_required
def rename_playlist(old_name):
    new_name = request.form['name']
    data = load_playlists()
    if old_name in data and new_name not in data:
        data[new_name] = data.pop(old_name)
        save_playlists(data)
    return redirect(url_for('playlists'))

@app.route('/playlist/reorder', methods=['POST'])
@login_required
def reorder_playlists():
    order = request.json.get('order', [])
    data = load_playlists()
    reordered = {name: data[name] for name in order if name in data}
    # Catch any names that weren't in the submitted order (shouldn't happen, but safe)
    for name in data:
        if name not in reordered:
            reordered[name] = data[name]
    save_playlists(reordered)
    return jsonify({"success": True})


# ------------- Player ------------------
@app.route('/playlist/<name>')
@login_required
def open_playlist(name):
    data = load_playlists()
    playlist = data.get(name, {"volume": 1.0, "tracks": []})
    return render_template(
        'player.html',
        tracks=playlist["tracks"],
        volume=playlist.get("volume", 1.0),
        playlist_name=name,
    )


@app.route('/playlist/save/<name>', methods=['POST'])
@login_required
def save_playlist(name):
    data = load_playlists()
    if name not in data:
        return jsonify({"error": "Playlist not found"}), 404

    playlist_folder = os.path.join(UPLOAD_FOLDER, name)
    os.makedirs(playlist_folder, exist_ok=True)

    tracks_metadata = json.loads(request.form.get('tracks', '[]'))
    volume = float(request.form.get('volume', data[name].get('volume', 1.0)))

    for t in tracks_metadata:
        file_field = f'file-{t["name"]}'
        if file_field in request.files:
            file = request.files[file_field]
            file_path = os.path.join(playlist_folder, file.filename)
            file.save(file_path)
            t['url'] = f'/static/uploads/{name}/{file.filename}'
        else:
            t['url'] = t.get('url', f'/static/audio/{t["name"]}')

    # Delete files for tracks that were removed
    old_filenames = {t['name'] for t in data[name]['tracks']}
    new_filenames = {t['name'] for t in tracks_metadata}
    for removed in old_filenames - new_filenames:
        path = os.path.join(playlist_folder, removed)
        if os.path.exists(path):
            os.remove(path)

    data[name] = {"volume": volume, "tracks": tracks_metadata}
    save_playlists(data)
    return jsonify({"success": True})


# ------------- Handle MIME Weirdness -----------------------
@app.route('/static/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('static/js', filename, mimetype='application/javascript')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)