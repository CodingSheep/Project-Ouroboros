// Library page: drag to reorder/move, open/close folders, inline name forms.
// The server returns the whole tree after every change, so this file only
// wires things up again after each swap (htmx.onLoad).
(function () {
    "use strict";

    const CLOSED_KEY = "library.closedFolders";

    function closedFolders() {
        try { return new Set(JSON.parse(localStorage.getItem(CLOSED_KEY) || "[]")); }
        catch (e) { return new Set(); }
    }

    function saveClosed(set) {
        try { localStorage.setItem(CLOSED_KEY, JSON.stringify([...set])); } catch (e) { /* private mode */ }
    }

    function csrfToken() {
        return JSON.parse(document.body.getAttribute("hx-headers"))["X-CSRFToken"];
    }

    function treeEl() { return document.getElementById("tree"); }

    function reloadTree() {
        htmx.ajax("GET", treeEl().dataset.treeUrl, { target: "#tree", swap: "innerHTML" });
    }

    function itemIds(list) {
        return [...list.children].filter((li) => li.dataset.id).map((li) => li.dataset.id);
    }

    function onDragEnd(evt) {
        document.body.classList.remove("dragging-folder", "dragging-playlist");
        if (evt.from === evt.to && evt.oldIndex === evt.newIndex) return;
        htmx.ajax("POST", treeEl().dataset.moveUrl, {
            target: "#tree",
            swap: "innerHTML",
            headers: { "X-CSRFToken": csrfToken() },
            values: {
                kind: evt.to.dataset.kind,
                id: evt.item.dataset.id,
                parent: evt.to.dataset.parent,
                order: itemIds(evt.to).join(","),
            },
        });
    }

    // root and everything inside it that matches (htmx hands us each swapped-in element).
    function within(root, selector) {
        if (!root.querySelectorAll) return [];
        return [...(root.matches(selector) ? [root] : []), ...root.querySelectorAll(selector)];
    }

    function setUp(root) {
        const closed = closedFolders();
        within(root, "li.folder").forEach((li) => {
            if (closed.has(li.dataset.id)) li.classList.add("closed");
        });
        within(root, "ul.sort").forEach((list) => {
            if (list.dataset.sortable) return;
            list.dataset.sortable = "1";
            const kind = list.dataset.kind;
            Sortable.create(list, {
                group: kind,              // folders and playlists never mix
                handle: ".handle",
                animation: 150,
                // Sortable's own drag (not the browser's): steadier with nested lists.
                forceFallback: true,
                fallbackOnBody: true,
                fallbackTolerance: 3,
                swapThreshold: 0.65,
                // Only react inside an empty folder's drop area, not near it, so
                // neighbouring lists don't both claim the item.
                emptyInsertThreshold: 0,
                onStart: (evt) => {
                    // A dragged folder shows only its own row, so the tree doesn't
                    // jump by the size of its contents as it moves.
                    evt.item.classList.add("is-dragged");
                    document.body.classList.add("dragging-" + kind);
                },
                onEnd: (evt) => {
                    evt.item.classList.remove("is-dragged");
                    onDragEnd(evt);
                },
            });
        });
        within(root, "#name-input").forEach((input) => { input.focus(); input.select(); });
    }

    function clearSlots(except) {
        document.querySelectorAll(".slot").forEach((s) => { if (s !== except) s.innerHTML = ""; });
    }

    document.addEventListener("click", (e) => {
        const toggle = e.target.closest(".toggle");
        if (toggle) {
            const li = toggle.closest("li.folder");
            const closed = closedFolders();
            if (li.classList.toggle("closed")) closed.add(li.dataset.id); else closed.delete(li.dataset.id);
            saveClosed(closed);
            return;
        }
        if (e.target.closest(".name-form .cancel")) clearSlots();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && e.target.closest(".name-form")) clearSlots();
    });

    document.addEventListener("htmx:beforeSwap", (e) => {
        // Only one name form open at a time.
        if (e.detail.target.classList.contains("slot")) clearSlots(e.detail.target);
        // Errors from a move (e.g. folder into its own subfolder): say why, then
        // show the tree as the server has it.
        if (e.detail.xhr.status >= 400) {
            alert(e.detail.xhr.responseText || "Something went wrong.");
            reloadTree();
        }
    });

    // Registered before htmx processes the page, so this also runs for the first load.
    htmx.onLoad(setUp);
})();
