import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import Folder, Playlist


def build_tree() -> tuple[list[dict], list[Playlist]]:
    """All folders as nested dicts {folder, children, playlists, n_playlists,
    n_tracks}, plus the playlists not in any folder. The n_ totals include
    everything inside (for the delete warning). Two queries, whatever the depth."""
    nodes = {f.pk: {"folder": f, "children": [], "playlists": []} for f in Folder.objects.all()}
    top, loose = [], []
    for node in nodes.values():
        parent = nodes.get(node["folder"].parent_id)
        (parent["children"] if parent else top).append(node)
    for p in Playlist.objects.annotate(track_count=Count("tracks")):
        (nodes[p.folder_id]["playlists"] if p.folder_id in nodes else loose).append(p)

    def total(node, seen=frozenset()):
        if node["folder"].pk in seen:   # cycle in bad data; don't recurse forever
            return 0, 0
        seen = seen | {node["folder"].pk}
        n_p, n_t = len(node["playlists"]), sum(p.track_count for p in node["playlists"])
        for child in node["children"]:
            cp, ct = total(child, seen)
            n_p, n_t = n_p + cp, n_t + ct
        node["n_playlists"], node["n_tracks"] = n_p, n_t
        return n_p, n_t

    for node in top:
        total(node)
    return top, loose


def render_tree(request, status=200):
    folders, loose = build_tree()
    return render(request, "library/_tree.html", {"folders": folders, "loose": loose}, status=status)


@login_required
def home(request):
    folders, loose = build_tree()
    return render(request, "library/home.html", {"folders": folders, "loose": loose})


@login_required
def tree(request):
    return render_tree(request)


# Create / rename. GET returns the inline form (swapped in by htmx); POST saves
# and returns the refreshed tree. A bad name re-shows the form with the error.

KINDS = {"folder": Folder, "playlist": Playlist}


def clean_name(request) -> tuple[str, str | None]:
    name = request.POST.get("name", "").strip()
    if not name:
        return name, "Enter a name."
    if len(name) > 200:
        return name, "Keep it under 200 characters."
    return name, None


def form_response(request, ctx, status=200):
    resp = render(request, "library/_name_form.html", ctx, status=status)
    if request.method == "POST":
        # Errors go back into the form, not the whole tree.
        resp["HX-Retarget"] = "#name-form"
        resp["HX-Reswap"] = "outerHTML"
    return resp


def get_parent_folder(value) -> Folder | None:
    return get_object_or_404(Folder, pk=value) if value else None


@login_required
@require_http_methods(["GET", "POST"])
def create(request, kind: str):
    model = KINDS.get(kind) or _404()
    parent = get_parent_folder(request.GET.get("parent") or request.POST.get("parent"))
    ctx = {"action": request.path, "kind": kind, "parent": parent, "name": "",
           "label": f"New {kind}" + (f" in {parent.name}" if parent else "")}
    if request.method == "GET":
        return form_response(request, ctx)
    name, error = clean_name(request)
    if error:
        return form_response(request, {**ctx, "name": name, "error": error})
    if model is Folder:
        Folder.objects.create(name=name, parent=parent)
    else:
        Playlist.objects.create(name=name, folder=parent)
    return render_tree(request)


@login_required
@require_http_methods(["GET", "POST"])
def rename(request, kind: str, pk: int):
    obj = get_object_or_404(KINDS.get(kind) or _404(), pk=pk)
    ctx = {"action": request.path, "kind": kind, "name": obj.name, "label": f"Rename {obj.name}"}
    if request.method == "GET":
        return form_response(request, ctx)
    name, error = clean_name(request)
    if error:
        return form_response(request, {**ctx, "name": name, "error": error})
    obj.name = name
    obj.save(update_fields=["name"] + (["updated"] if kind == "playlist" else []))
    return render_tree(request)


@login_required
@require_POST
def delete(request, kind: str, pk: int):
    """Deletes the folder/playlist and everything inside, audio files included
    (see the post_delete signal in models.py). The page asks first."""
    get_object_or_404(KINDS.get(kind) or _404(), pk=pk).delete()
    return render_tree(request)


@login_required
@require_POST
def move(request):
    """After a drag: put item (kind, id) into folder `parent` ("" = top level)
    and set the order of that container's items of the same kind from `order`
    (comma-separated ids). Returns the refreshed tree."""
    kind = request.POST.get("kind")
    model = KINDS.get(kind) or _404()
    obj = get_object_or_404(model, pk=request.POST.get("id"))
    parent = get_parent_folder(request.POST.get("parent"))
    try:
        order = [int(x) for x in request.POST.get("order", "").split(",") if x]
    except ValueError:
        return HttpResponseBadRequest("Bad order.")
    with transaction.atomic():
        if model is Folder:
            obj.parent = parent
            try:
                obj.clean()
            except ValidationError as e:
                return HttpResponseBadRequest(" ".join(e.messages))
            obj.save(update_fields=["parent"])
            siblings = Folder.objects.filter(parent=parent)
        else:
            obj.folder = parent
            obj.save(update_fields=["folder", "updated"])
            siblings = Playlist.objects.filter(folder=parent)
        # Listed ids first in that order, then anything not listed (keeps its order).
        current = list(siblings.values_list("pk", flat=True))
        ids = [pk for pk in dict.fromkeys(order) if pk in current]
        rest = [pk for pk in current if pk not in ids]
        for position, pk in enumerate(ids + rest):
            model.objects.filter(pk=pk).update(position=position)
    return render_tree(request)


def _404():
    raise Http404


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
