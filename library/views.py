import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render

from .models import Folder, Playlist


def build_tree() -> tuple[list[dict], list[Playlist]]:
    """All folders as nested dicts {folder, children, playlists}, plus the
    playlists not in any folder. Two queries, whatever the depth."""
    nodes = {f.pk: {"folder": f, "children": [], "playlists": []} for f in Folder.objects.all()}
    top, loose = [], []
    for node in nodes.values():
        parent = nodes.get(node["folder"].parent_id)
        (parent["children"] if parent else top).append(node)
    for p in Playlist.objects.annotate(track_count=Count("tracks")):
        (nodes[p.folder_id]["playlists"] if p.folder_id in nodes else loose).append(p)
    return top, loose


@login_required
def home(request):
    folders, loose = build_tree()
    return render(request, "library/home.html", {"folders": folders, "loose": loose})


@login_required
def media(request, path: str):
    """Uploaded audio, for logged-in users only.

    On the server nginx sends the file (X-Accel-Redirect), which handles range
    requests for seeking. Without nginx (development) Django sends it.
    """
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise Http404
    rel = target.relative_to(root).as_posix()
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if settings.MEDIA_ACCEL_PREFIX:
        resp = HttpResponse(content_type=content_type)
        resp["X-Accel-Redirect"] = settings.MEDIA_ACCEL_PREFIX.rstrip("/") + "/" + quote(rel)
        return resp
    return FileResponse(open(target, "rb"), content_type=content_type)
