# integrations/local_image_generator.py
# Generates images through the local image-generator CLI.

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config.settings import LOCAL_IMAGE_GENERATOR_PATH


def generate_image(
    *,
    prompt: str,
    width: int = 512,
    height: int = 512,
    quality: str = "standard",
) -> dict:
    """Generate one image through the local image generator."""
    command = [
        str(LOCAL_IMAGE_GENERATOR_PATH),
        "--prompt",
        prompt,
        "--count",
        "1",
        "--quality",
        quality,
        "--width",
        str(width),
        "--height",
        str(height),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Local image generation failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    metadata = _extract_metadata(result.stdout)

    images = metadata.get("images")
    if not images:
        raise RuntimeError("Local image generator returned no images.")

    generator_path = Path(LOCAL_IMAGE_GENERATOR_PATH).resolve()
    output_path = (
        generator_path.parent
        / "output"
        / metadata["job_id"]
        / images[0]["file"]
    )

    if not output_path.is_file():
        raise RuntimeError(
            f"Generated image file not found: {output_path}"
        )

    return {
        "provider": "local",
        "model": "stable-diffusion-v1-5",
        "width": metadata["width"],
        "height": metadata["height"],
        "file_path": str(output_path),
    }


def _extract_metadata(output: str) -> dict:
    """Extract the final JSON object from CLI output."""
    json_start = output.find("{")

    if json_start == -1:
        raise RuntimeError(
            "Local image generator returned no metadata."
        )

    try:
        return json.loads(output[json_start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid metadata returned by local image generator."
        ) from exc