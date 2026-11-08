"""Folders hold folders and playlists (any depth); playlists hold tracks.

Audio files are stored under generated names (tracks/<random>.mp3), and the
original filename is kept as the track's display name. So renaming or moving a
playlist never touches files, and deleting a track (or anything containing it)
deletes its file.
"""
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

AUDIO_EXTENSIONS = ["mp3", "ogg", "opus", "wav", "flac", "m4a", "aac", "webm"]


class Positioned(models.Model):
    """Ordered among its siblings. A new item goes to the end."""

    position = models.PositiveIntegerField(blank=True)

    class Meta:
        abstract = True

    def siblings(self) -> models.QuerySet:
        raise NotImplementedError

    def save(self, *args, **kwargs):
        if self.position is None:
            last = self.siblings().aggregate(m=models.Max("position"))["m"]
            self.position = 0 if last is None else last + 1
        super().save(*args, **kwargs)


class Folder(Positioned):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="children")

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.path()

    def siblings(self):
        return Folder.objects.filter(parent=self.parent).exclude(pk=self.pk)

    def ancestors(self) -> list["Folder"]:
        """Parent first, then up to the top."""
        out, node, seen = [], self.parent, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            out.append(node)
            node = node.parent
        return out

    def path(self) -> str:
        return " / ".join([f.name for f in reversed(self.ancestors())] + [self.name])

    def clean(self):
        # A folder can't go inside itself or one of its own subfolders.
        if self.parent_id and self.pk:
            if self.parent_id == self.pk or any(a.pk == self.pk for a in self.parent.ancestors()):
                raise ValidationError({"parent": "A folder can't be moved inside itself."})


class Playlist(Positioned):
    name = models.CharField(max_length=200)
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="playlists")
    volume = models.FloatField(default=1.0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return f"{self.folder.path()} / {self.name}" if self.folder else self.name

    def siblings(self):
        return Playlist.objects.filter(folder=self.folder).exclude(pk=self.pk)


def track_upload_path(instance: "Track", filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return f"tracks/{uuid.uuid4().hex}{ext}"


class Track(Positioned):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(max_length=255, help_text="Shown in the player; usually the original filename.")
    file = models.FileField(upload_to=track_upload_path, max_length=255,
                            validators=[FileExtensionValidator(AUDIO_EXTENSIONS)])
    loop = models.BooleanField(default=False, help_text="Repeat this track instead of moving on.")

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.name

    def siblings(self):
        return Track.objects.filter(playlist=self.playlist).exclude(pk=self.pk)


@receiver(post_delete, sender=Track)
def delete_track_file(sender, instance: Track, **kwargs):
    """Runs for direct deletes and for deletes cascading from a playlist or folder."""
    if instance.file:
        instance.file.delete(save=False)
