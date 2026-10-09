# social/post_images.py
# Resolves generated image ids to safe file paths on disk.

from __future__ import annotations

import logging
from pathlib import Path

from config.settings import IMAGE_OUTPUT_ROOT
from database.posts import get_generated_image_file_path

logger = logging.getLogger(__name__)


def resolve_generated_image_path(image_id: int) -> Path | None:
    """Return the image file for an id, or None if missing or outside the output folder."""
    stored_path = get_generated_image_file_path(image_id)
    if not stored_path:
        return None

    # Resolving first neutralizes ".." and symlinks before the containment check.
    image_path = Path(stored_path).resolve()
    output_root = Path(IMAGE_OUTPUT_ROOT).resolve()
    if not image_path.is_relative_to(output_root) or not image_path.is_file():
        logger.warning("Image #%s not usable: %s", image_id, image_path)
        return None

    return image_path