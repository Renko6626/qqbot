"""Attach recognition metadata when writing a hit to the shared albums."""
from qqbot.albums import AlbumStore
from qqbot.image_rating.service import ImageAnalysis


def save_hit(analysis: ImageAnalysis, albums: AlbumStore, album: str, *,
             group_id: int, message_id: int) -> dict:
    metadata = {"group_id": str(group_id), "message_id": str(message_id),
                "label": analysis.result.label, "scores": analysis.result.scores,
                "first_frame_only": analysis.result.first_frame_only}
    if analysis.gate is not None:
        metadata["gate"] = {"label": analysis.gate.label, "scores": analysis.gate.scores}
    return albums.add_image(album, analysis.data, source="anime_rating_watch", metadata=metadata)
