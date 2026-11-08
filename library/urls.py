from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.home, name="home"),
    path("tree/", views.tree, name="tree"),
    path("move/", views.move, name="move"),
    path("<str:kind>/new/", views.create, name="create"),
    path("<str:kind>/<int:pk>/rename/", views.rename, name="rename"),
    path("<str:kind>/<int:pk>/delete/", views.delete, name="delete"),
]
