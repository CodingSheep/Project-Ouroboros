from django.contrib import admin
from django.db.models import Count

from .models import Folder, Playlist, Track


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ["__str__", "position", "playlist_count"]
    search_fields = ["name"]
    list_select_related = ["parent"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count("playlists"))

    @admin.display(description="Playlists", ordering="n")
    def playlist_count(self, obj):
        return obj.n


class TrackInline(admin.TabularInline):
    model = Track
    fields = ["position", "name", "file", "loop"]
    extra = 0


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ["name", "folder", "position", "volume", "track_count", "updated"]
    list_filter = ["folder"]
    search_fields = ["name"]
    list_select_related = ["folder"]
    inlines = [TrackInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count("tracks"))

    @admin.display(description="Tracks", ordering="n")
    def track_count(self, obj):
        return obj.n


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ["name", "playlist", "position", "loop"]
    search_fields = ["name", "playlist__name"]
    list_select_related = ["playlist"]
