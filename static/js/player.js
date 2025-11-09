// static/js/player.js
export const tracks = [];

export function createTrack(file, url, el) {
    const audio = new Audio(url);
    audio.preload = 'auto';
    audio.loop = false;

    const name = file ? file.name : el.querySelector('.name').textContent;

    const track = { file, url, audio, el, name };
    return track;
}

export function playTrack(track) {
    const playBtn = track.el.querySelector('.play');

    if (!track.audio.paused) {
        // Track is currently playing → pause it
        track.audio.pause();
        if (playBtn)
            playBtn.textContent = 'Play';
        return;
    }

    // Pause all other tracks but leave .playing class only on active track
    tracks.forEach(t => {
        if (t !== track) {
            t.audio.pause();
            t.audio.currentTime = 0;
            t.el.classList.remove('playing');   // remove visual from other tracks
            const btn = t.el.querySelector('.play');
            if (btn)
                btn.textContent = 'Play';
        }
    });

    // Play the clicked track
    track.audio.play();
    track.el.classList.add('playing');       // visual stays
    if (playBtn)
        playBtn.textContent = 'Pause';
}


export function pauseTrack(track) {
    track.audio.pause();
    track.el.classList.remove('playing');
}

export function stopAll() {
    tracks.forEach(t => {
        t.audio.pause();
        t.audio.currentTime = 0;
    });
}

export function nextTrack(currentTrackEl) {
    const children = Array.from(currentTrackEl.parentElement.children);
    const idx = children.indexOf(currentTrackEl);
    if (idx >= 0 && idx < children.length - 1) {
        const nextDiv = children[idx + 1];
        const track = tracks.find(t => t.el === nextDiv);
        if (track)
            playTrack(track);
        return track;
    }
    return null;
}

export function updateVolume(value) {
    tracks.forEach(t => t.audio.volume = value);
}
