from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.home, name="home"),
    path("tree/", views.tree, name="tree"),
    path("move/", views.move, name="move"),
    path("playlist/<int:pk>/", views.player, name="player"),
    path("playlist/<int:pk>/upload/", views.upload, name="upload"),
    path("playlist/<int:pk>/order/", views.track_order, name="track_order"),
    path("playlist/<int:pk>/volume/", views.playlist_volume, name="volume"),
    path("track/<int:pk>/loop/", views.track_loop, name="track_loop"),
    path("track/<int:pk>/delete/", views.track_delete, name="track_delete"),
    path("<str:kind>/new/", views.create, name="create"),
    path("<str:kind>/<int:pk>/rename/", views.rename, name="rename"),
    path("<str:kind>/<int:pk>/delete/", views.delete, name="delete"),
]
