import io
import logging
import os
from pathlib import Path
from typing import Any
from PIL import Image

logger = logging.getLogger("comic-generator")

_model_cache: Any = None


def _ensure_scenes_available():
    if not (Path.cwd() / "docs" / "scenes").exists():
        candidates = [
            Path(os.path.expanduser("~/ZERO/image-models/xkcd-artist-source")),
            Path(os.path.expanduser("~/ZERO")),
            Path(os.path.expanduser("~/ZERO/comic-service")),
            Path("/home/opffarmy/ZERO/image-models/xkcd-artist-source"),
        ]
        for c in candidates:
            if (c / "docs" / "scenes").exists():
                try:
                    os.chdir(str(c))
                    logger.info(f"Changed working directory to {c} to access docs/scenes")
                except Exception:
                    pass
                break


def get_model():
    global _model_cache
    if _model_cache is None:
        try:
            _ensure_scenes_available()
            # Import from the XKCD Artist python source
            from xkcd_artist import xkcd_artist
            _model_cache = xkcd_artist
            logger.info("Successfully initialized XKCD Artist ONNX model backend.")
        except Exception as exc:
            logger.error(f"Failed to import xkcd_artist: {exc}")
            raise RuntimeError(f"XKCD Artist import failure: {exc}") from exc
    return _model_cache


def generate_comic_png(prompt: str, backend: str = "onnx") -> Image.Image:
    """Generate a comic PIL Image using the existing ONNX planner & Pillow renderer."""
    _ensure_scenes_available()
    artist_fn = get_model()
    
    # Generate comic object using ONNX backend
    comic = artist_fn(prompt, backend=backend)
    
    if hasattr(comic, "to_png"):
        raw_png = comic.to_png()
        if isinstance(raw_png, bytes):
            return Image.open(io.BytesIO(raw_png))
        elif isinstance(raw_png, Image.Image):
            return raw_png
            
    if hasattr(comic, "image"):
        return comic.image
    elif isinstance(comic, Image.Image):
        return comic

    raise RuntimeError(f"Unexpected output type from xkcd_artist: {type(comic)}")

