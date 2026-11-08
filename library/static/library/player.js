// Player page. One track plays at a time. When a track ends it repeats if
// Repeat is on (checked at the end, so it can be switched while playing),
// otherwise the next track starts. Every change is saved straight away.
(function () {
    "use strict";

    const root = document.getElementById("player");
    const list = document.getElementById("tracks");
    const volume = document.getElementById("volume");
    const volumeLabel = document.getElementById("volume-label");
    const status = document.getElementById("status");
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");

    const tracks = new Map();   // <li> -> {audio, ...}
    let current = null;         // the <li> playing or paused mid-track

    // ---- Saving ----

    function csrfToken() {
        return JSON.parse(document.body.getAttribute("hx-headers"))["X-CSRFToken"];
    }

    let statusTimer = null;
    function say(text, isError) {
        status.textContent = text;
        status.classList.toggle("error", !!isError);
        clearTimeout(statusTimer);
        if (!isError) statusTimer = setTimeout(() => { status.textContent = ""; }, 2000);
    }

    async function post(url, data) {
        const body = data instanceof FormData ? data : new URLSearchParams(data);
        let resp;
        try {
            resp = await fetch(url, { method: "POST", body, headers: { "X-CSRFToken": csrfToken() } });
        } catch (e) {
            say("Not saved: can't reach the server.", true);
            throw e;
        }
        if (!resp.ok) {
            const text = resp.status === 403 ? "Not saved: log in again (reload the page)." : await resp.text();
            say(text || "Not saved (error " + resp.status + ").", true);
            throw new Error(text);
        }
        return resp;
    }

    // ---- Playback ----

    function formatTime(seconds) {
        if (!isFinite(seconds)) return "0:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60).toString().padStart(2, "0");
        return m + ":" + s;
    }

    function showPlaying(li, playing) {
        li.classList.toggle("playing", playing);
        li.querySelector(".play").textContent = playing ? "Pause" : "Play";
    }

    function stop(li) {
        const t = tracks.get(li);
        if (!t) return;
        t.audio.pause();
        t.audio.currentTime = 0;
        showPlaying(li, false);
        li.classList.remove("current");
    }

    function play(li) {
        if (current && current !== li) stop(current);
        current = li;
        li.classList.add("current");
        const t = tracks.get(li);
        t.audio.play().then(() => showPlaying(li, true), (e) => say("Can't play: " + e.message, true));
    }

    function stopAll() {
        tracks.forEach((t, li) => stop(li));
        current = null;
    }

    function nextTrack(li) {
        let next = li.nextElementSibling;
        while (next && !tracks.has(next)) next = next.nextElementSibling;
        return next;
    }

    function setLoopButton(li, loop) {
        const btn = li.querySelector(".loop");
        btn.textContent = loop ? "Repeat On" : "Repeat Off";
        btn.classList.toggle("on", loop);
        btn.setAttribute("aria-pressed", loop ? "true" : "false");
    }

    // ---- Track rows ----

    function wire(li) {
        const audio = new Audio(li.dataset.url);
        audio.preload = "auto";
        audio.loop = li.dataset.loop === "1";
        audio.volume = parseFloat(volume.value);
        const progress = li.querySelector(".progress");
        const time = li.querySelector(".time");
        let seeking = false;
        tracks.set(li, { audio });
        setLoopButton(li, audio.loop);

        const showTime = () => {
            time.textContent = formatTime(audio.currentTime) + " / " + formatTime(audio.duration);
            if (!seeking && audio.duration) progress.value = (audio.currentTime / audio.duration) * 1000;
        };
        audio.addEventListener("loadedmetadata", showTime);
        audio.addEventListener("timeupdate", showTime);
        audio.addEventListener("pause", () => showPlaying(li, false));
        audio.addEventListener("play", () => showPlaying(li, true));
        audio.addEventListener("error", () => say("Can't load " + li.querySelector(".name").textContent, true));
        audio.addEventListener("ended", () => {
            // Only fires when Repeat is off (audio.loop repeats by itself).
            stop(li);
            current = null;
            const next = nextTrack(li);
            if (next) play(next);
        });

        li.querySelector(".play").addEventListener("click", () => {
            if (audio.paused) play(li); else audio.pause();
        });

        li.querySelector(".loop").addEventListener("click", () => {
            audio.loop = !audio.loop;
            setLoopButton(li, audio.loop);
            post(li.dataset.loopUrl, { loop: audio.loop ? "1" : "0" }).then(() => say("Saved"), () => {
                audio.loop = !audio.loop;   // put it back as the server has it
                setLoopButton(li, audio.loop);
            });
        });

        progress.addEventListener("input", () => {
            seeking = true;
            if (audio.duration) time.textContent = formatTime(progress.value / 1000 * audio.duration) + " / " + formatTime(audio.duration);
        });
        progress.addEventListener("change", () => {
            if (audio.duration) audio.currentTime = progress.value / 1000 * audio.duration;
            seeking = false;
        });

        li.querySelector(".remove").addEventListener("click", () => {
            const name = li.querySelector(".name").textContent;
            if (!confirm("Remove “" + name + "”? Its audio file is deleted too.")) return;
            post(li.dataset.deleteUrl, {}).then(() => {
                if (current === li) current = null;
                audio.pause();
                audio.removeAttribute("src");
                tracks.delete(li);
                li.remove();
                say("Removed " + name);
            }, () => {});
        });
    }

    list.querySelectorAll("li.track").forEach(wire);

    Sortable.create(list, {
        handle: ".handle",
        animation: 150,
        forceFallback: true,
        fallbackTolerance: 3,
        onEnd: (evt) => {
            if (evt.oldIndex === evt.newIndex) return;
            const order = [...list.children].map((li) => li.dataset.id).join(",");
            post(root.dataset.orderUrl, { order }).then(() => say("Saved"), () => {});
        },
    });

    // ---- Volume (all tracks; saved for this playlist) ----

    let volumeTimer = null;
    function showVolume() {
        volumeLabel.textContent = Math.round(volume.value * 100) + "%";
    }
    volume.addEventListener("input", () => {
        const v = parseFloat(volume.value);
        tracks.forEach((t) => { t.audio.volume = v; });
        showVolume();
        clearTimeout(volumeTimer);
        volumeTimer = setTimeout(() => post(root.dataset.volumeUrl, { volume: v }).then(() => say("Saved"), () => {}), 400);
    });
    showVolume();

    document.getElementById("stop-all").addEventListener("click", stopAll);

    // ---- Adding files: each uploads once, in the order given ----

    let queue = Promise.resolve();
    function addFiles(files) {
        [...files].forEach((file) => {
            queue = queue.then(async () => {
                say("Uploading " + file.name + "…");
                const form = new FormData();
                form.append("file", file);
                try {
                    const resp = await post(root.dataset.uploadUrl, form);
                    const tpl = document.createElement("template");
                    tpl.innerHTML = (await resp.text()).trim();
                    const li = tpl.content.firstElementChild;
                    list.appendChild(li);
                    wire(li);
                    say("Added " + file.name);
                } catch (e) { /* say() already showed why */ }
            });
        });
    }

    document.getElementById("browse").addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", () => {
        addFiles(fileInput.files);
        fileInput.value = "";
    });

    // Files dropped anywhere on the page are added (and the browser doesn't
    // navigate away to play the file itself).
    const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
    window.addEventListener("dragover", (e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        dropzone.classList.add("hover");
    });
    window.addEventListener("dragleave", (e) => {
        if (!e.relatedTarget) dropzone.classList.remove("hover");
    });
    window.addEventListener("drop", (e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        dropzone.classList.remove("hover");
        addFiles(e.dataTransfer.files);
    });
})();
