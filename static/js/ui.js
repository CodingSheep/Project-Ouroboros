// static/js/ui.js
import { tracks, createTrack, playTrack, pauseTrack, stopAll, nextTrack, updateVolume } from './player.js';
import { formatTime, reorderArrayByDom } from './utils.js';

// Autosave Functionality
let autoSaveTimeout = null;
function autoSave() {
    clearTimeout(autoSaveTimeout);
    autoSaveTimeout = setTimeout(savePlaylist, 500);
}

const dropzone = document.getElementById('dropzone');
const playlist = document.getElementById('playlist');
const volumeSlider = document.getElementById('volume');
const stopAllBtn = document.getElementById('stopAll');
const fileInput = document.getElementById('fileInput');
const openFilesBtn = document.getElementById('openFiles');
const saveBtn = document.getElementById('savePlaylist');

const loadedTrackNames = new Set();


// Initialization
if (typeof initialTracks !== 'undefined') {
    initialTracks.forEach(trackData => addTrackFromData(trackData));
}

if (typeof initialVolume !== 'undefined') {
    volumeSlider.value = initialVolume;
}
updateVolume(parseFloat(volumeSlider.value));

// Global Controls
volumeSlider.addEventListener('input', () => {
    const value = parseFloat(volumeSlider.value);
    updateVolume(value);                       // existing function to set audio volume
    volumeLabel.textContent = `${Math.round(value * 100)}%`;
});
volumeLabel.textContent = `${Math.round(volumeSlider.value * 100)}%`;

stopAllBtn.addEventListener('click', stopAll);
saveBtn.addEventListener('click', () => {
    savePlaylist(true);
});

// Drag and Drop
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    window.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
    }, false);
});

// Dropzone Hover Visual Feedback
['dragenter', 'dragover'].forEach(ev => {
    dropzone.addEventListener(ev, e => {
        dropzone.classList.add('hover');
        if (e.dataTransfer)
            e.dataTransfer.dropEffect = 'copy';
    });
});
['dragleave', 'drop'].forEach(ev => {
    dropzone.addEventListener(ev, e => dropzone.classList.remove('hover'));
});

// Dropzone File Handling
dropzone.addEventListener('drop', e => {
    const items = e.dataTransfer?.items;
    if (items && items.length) {
        for (const it of items) {
            if (it.kind === 'file') {
                const f = it.getAsFile();
                if (f && f.type.startsWith('audio/'))
                    addTrackFromData({ file: f, name: f.name, loop: false });
            }
        }
    } else {
        // Fallback to files
        const files = e.dataTransfer?.files || [];
        for (const f of files)
            if (f.type.startsWith('audio/'))
                addTrackFromData({ file: f, name: f.name, loop: false });
    }
});

// Click-to-open File Picker
loopBtn.addEventListener('click', () => {
    track.audio.loop = !track.audio.loop;
    loopBtn.textContent = track.audio.loop ? 'Repeat On' : 'Repeat Off';
    loopBtn.className = track.audio.loop ? 'loop-on' : 'loop-off';
    autoSave();
});

fileInput.addEventListener('change', () => {
    for (const f of fileInput.files)
        addTrackFromData({ file: f, name: f.name, loop: false });
    fileInput.value = '';
});

function addTrackFromData(trackData) {
    // Prevent Duplicate Tracks from loading in memory
    if (loadedTrackNames.has(trackData.name))
        return;
    loadedTrackNames.add(trackData.name);

    const file = trackData.file || null;

    const url = trackData.url || (file ? URL.createObjectURL(file) : null);
    if (!url)
        return;

    const div = document.createElement('div');
    div.className = 'track';
    div.draggable = false;
    div.innerHTML = `
    <div class="left">
        <div class="drag-handle">≡</div>
        <div class="name" title="${trackData.name}">${trackData.name}</div>
    </div>
    <div class="controls">
        <button class="play">Play</button>
        <button class="${trackData.loop ? 'loop-on' : 'loop-off'}">${trackData.loop ? 'Repeat On' : 'Repeat Off'}</button>
        <button class="remove">Remove</button>
        <input type="range" class="progress" min="0" max="100" value="0" step="0.1" />
        <span class="time">0:00 / 0:00</span>
    </div>
  `;
    playlist.appendChild(div);

    const track = createTrack(file, url, div);
    track.audio.loop = trackData.loop;
    track.name = trackData.name;

    const playBtn = div.querySelector('.play');
    const loopBtn = div.querySelector('.loop-on, .loop-off');
    const removeBtn = div.querySelector('.remove');
    const progress = div.querySelector('.progress');
    const timeDisplay = div.querySelector('.time');
    const handle = div.querySelector('.drag-handle');

    // Play/Pause
    playBtn.addEventListener('click', () => {
        if (track.audio.paused)
            playTrack(track), playBtn.textContent = 'Pause';
        else
            pauseTrack(track), playBtn.textContent = 'Play';
    });

    // Loop Toggle
    loopBtn.addEventListener('click', () => {
        track.audio.loop = !track.audio.loop;
        loopBtn.textContent = track.audio.loop ? 'Repeat On' : 'Repeat Off';
        loopBtn.className = track.audio.loop ? 'loop-on' : 'loop-off';
    });

    // Remove Track
    removeBtn.addEventListener('click', () => {
        track.audio.pause();
        track.audio.currentTime = 0;
        if (file) URL.revokeObjectURL(track.url);
        playlist.removeChild(div);
        const idx = tracks.indexOf(track);
        if (idx > -1) tracks.splice(idx, 1);
        loadedTrackNames.delete(trackData.name);
        autoSave();
    });

    // Time/Progress
    track.audio.addEventListener('timeupdate', () => {
        if (!progress.dragging)
            progress.value = (track.audio.currentTime / track.audio.duration) * 100 || 0;
        timeDisplay.textContent = `${formatTime(track.audio.currentTime)} / ${formatTime(track.audio.duration)}`;
    });

    track.audio.addEventListener('loadedmetadata', () => timeDisplay.textContent = `0:00 / ${formatTime(track.audio.duration)}`);
    track.audio.addEventListener('ended', () => {
        playBtn.textContent = 'Play';
        if (!track.audio.loop) {
            const next = nextTrack(div);
            if (next) {
                const nextBtn = next.el.querySelector('.play');
                if (nextBtn)
                    nextBtn.textContent = 'Pause';
            }
        }
    });

    progress.addEventListener('mousedown', e => e.stopPropagation());
    progress.addEventListener('touchstart', e => e.stopPropagation());
    progress.addEventListener('pointerdown', e => e.stopPropagation());
    progress.addEventListener('input', () => progress.dragging = true);
    progress.addEventListener('change', () => {
        if (track.audio.duration)
            track.audio.currentTime = (progress.value / 100) * track.audio.duration;
        progress.dragging = false;
    });

    // Drag Handle
    handle.addEventListener('mousedown', e => {
        // Only allow dragging the track when clicking the handle
        div.draggable = true;
    });
    handle.addEventListener('dragend', e => {
        // Optional: prevent accidental dragging after release
        div.draggable = false;
    });

    tracks.push(track);
    enableDragSorting();
    autoSave();
}

// Drag Sorting
function enableDragSorting() {
    const items = playlist.querySelectorAll('.track');
    let dragging = null;

    items.forEach(item => {
        // Remove old event listeners to avoid duplicates
        item.removeEventListener('dragstart', onDragStart);
        item.removeEventListener('dragover', onDragOver);
        item.removeEventListener('drop', onDrop);
        item.removeEventListener('dragend', onDragEnd);

        // Add drag listeners
        item.addEventListener('dragstart', onDragStart);
        item.addEventListener('dragover', onDragOver);
        item.addEventListener('drop', onDrop);
        item.addEventListener('dragend', onDragEnd);
    });

    function onDragStart(e) {
        // Only proceed if the element is currently draggable
        if (!this.draggable)
            return;
        dragging = this;
        e.dataTransfer.setData('text/plain', 'drag'); // required for Firefox
        this.style.opacity = '0.6';
    }

    function onDragOver(e) {
        e.preventDefault();

        items.forEach(it => {
            it.style['border-top'] = '';
            it.style['border-bottom'] = '';
        });

        const rect = this.getBoundingClientRect();
        const offset = e.clientY - rect.top;
        const half = rect.height / 2;
        if (offset > half)
            this.style['border-bottom'] = '2px solid #66d7ff';
        else
            this.style['border-top'] = '2px solid #66d7ff';
    }

    function onDrop(e) {
        e.preventDefault();
        const target = this;

        if (!dragging || dragging === target) return;

        // Clear borders
        items.forEach(it => {
            it.style['border-top'] = '';
            it.style['border-bottom'] = '';
        });

        const nodes = Array.from(playlist.children);
        const dragIndex = nodes.indexOf(dragging);
        const dropIndex = nodes.indexOf(target);
        const rect = target.getBoundingClientRect();
        const offset = e.clientY - rect.top;
        const half = rect.height / 2;

        if (dragIndex < dropIndex)
            playlist.insertBefore(dragging, offset > half ? target.nextSibling : target);
        else
            playlist.insertBefore(dragging, offset > half ? target.nextSibling : target);

        reorderArrayByDom(tracks, nodes, t => t.el);
        autoSave();
    }

    function onDragEnd() {
        this.style.opacity = '';
        items.forEach(it => {
            it.style['border-top'] = '';
            it.style['border-bottom'] = '';
        });
        dragging = null;
    }
}

// ---------- Save Playlist ----------
async function savePlaylist(showAlert = false) {
    const formData = new FormData();
    const tracksData = tracks.map(t => ({
        name: t.name,
        loop: t.audio.loop,
        url: t.url
    }));

    tracks.forEach(t => {
        if (t.file) formData.append(`file-${t.name}`, t.file);
    });

    formData.append('tracks', JSON.stringify(tracksData));
    formData.append('volume', volumeSlider.value);

    const resp = await fetch(`/playlist/save/${playlistName}`, {
        method: 'POST',
        body: formData
    });

    const data = await resp.json();
    if (showAlert) {
        if (data.success) alert('Playlist saved!');
        else alert('Error saving playlist');
    }
}

