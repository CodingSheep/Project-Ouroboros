from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import json
import os

app = Flask(__name__)
PLAYLIST_FILE = 'playlists.json'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load playlists
def load_playlists():
    if os.path.exists(PLAYLIST_FILE):
        with open(PLAYLIST_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save playlists
def save_playlists(data):
    with open(PLAYLIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ----------------- Playlist Management --------------------
@app.route('/')
def playlists():
    data = load_playlists()
    return render_template('playlists.html', playlists=data)

@app.route('/playlist/add', methods=['POST'])
def add_playlist():
    name = request.form['name']
    data = load_playlists()
    if name in data:
        return jsonify({"error": "Playlist already exists"}), 400
    data[name] = []
    save_playlists(data)
    return redirect(url_for('playlists'))

@app.route('/playlist/delete/<name>', methods=['POST'])
def delete_playlist(name):
    data = load_playlists()
    if name in data:
        data.pop(name)
        save_playlists(data)
    return redirect(url_for('playlists'))

@app.route('/playlist/rename/<old_name>', methods=['POST'])
def rename_playlist(old_name):
    new_name = request.form['name']
    data = load_playlists()
    if old_name in data and new_name not in data:
        data[new_name] = data.pop(old_name)
        save_playlists(data)
    return redirect(url_for('playlists'))

# ------------- Player ------------------
@app.route('/playlist/<name>')
def open_playlist(name):
    data = load_playlists()
    playlist = data.get(name, [])
    return render_template('player.html', tracks=playlist, playlist_name=name)

# ---------- Save Playlist Changes (tracks order, loop state) ----------
@app.route('/playlist/save/<name>', methods=['POST'])
def save_playlist(name):
    data = load_playlists()
    if name not in data:
        return jsonify({"error": "Playlist not found"}), 404

    playlist_folder = os.path.join(UPLOAD_FOLDER, name)
    os.makedirs(playlist_folder, exist_ok=True)

    # Expect files via request.files and track metadata via JSON in 'tracks' field
    tracks_metadata = json.loads(request.form.get('tracks', '[]'))

    # Save uploaded files and update URLs
    for t in tracks_metadata:
        # Check if a file was uploaded for this track
        file_field = f'file-{t["name"]}'
        if file_field in request.files:
            file = request.files[file_field]
            file_path = os.path.join(playlist_folder, file.filename)
            file.save(file_path)
            t['url'] = f'/static/uploads/{name}/{file.filename}'
        else:
            # Keep existing URL if no new file uploaded
            t['url'] = t.get('url', f'/static/audio/{t["name"]}')

    # Save playlist JSON
    data[name] = tracks_metadata
    save_playlists(data)
    return jsonify({"success": True})

# ------------- Handle MIME Weirdness -----------------------
@app.route('/static/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('static/js', filename, mimetype='application/javascript')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)