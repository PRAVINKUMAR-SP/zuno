"""
ZERO XKCD Comic Generation Service
Single-file microservice running on Ubuntu at port 8002.

Usage on Ubuntu:
    source ~/ZERO/hf-venv/bin/activate
    python ~/ZERO/comic_server.py
"""

import io
import logging
import os
from pathlib import Path
import sys
import uuid
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

# Ensure the xkcd-artist source code is on sys.path and CWD is set so docs/scenes can be found
XKCD_SOURCE = Path(os.path.expanduser("~/ZERO/image-models/xkcd-artist-source/python/src"))
if XKCD_SOURCE.exists() and str(XKCD_SOURCE) not in sys.path:
    sys.path.insert(0, str(XKCD_SOURCE))

# Find and switch to directory containing docs/scenes so xkcd_artist can open scene PNGs
_candidates = [
    Path(os.path.expanduser("~/ZERO/image-models/xkcd-artist-source")),
    Path(os.path.expanduser("~/ZERO")),
    Path(os.path.expanduser("~/ZERO/comic-service")),
    Path.cwd(),
]
for _c in _candidates:
    if (_c / "docs" / "scenes").exists():
        os.chdir(str(_c))
        break

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("zero-comic-service")

OUTPUT_DIR = Path(os.getenv("COMIC_OUTPUT_DIR", Path.home() / "ZERO" / "comic-output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ZERO XKCD Comic Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve output PNGs
app.mount("/images", StaticFiles(directory=str(OUTPUT_DIR)), name="images")


class ComicRequest(BaseModel):
    request_id: str | None = Field(default=None)
    prompt: str = Field(..., min_length=3)
    title: str | None = Field(default="Comic")
    panels: int | None = Field(default=4)


class ComicResponse(BaseModel):
    success: bool
    request_id: str
    image_url: str | None = None
    filename: str | None = None
    title: str | None = None
    prompt: str | None = None
    format: str = "png"
    width: int | None = None
    height: int | None = None
    error: str | None = None


_artist_fn = None


def get_artist():
    global _artist_fn
    if _artist_fn is None:
        try:
            from xkcd_artist import xkcd_artist
            _artist_fn = xkcd_artist
            logger.info("Successfully imported xkcd_artist ONNX module.")
        except Exception as exc:
            logger.error(f"Failed to import xkcd_artist: {exc}")
            raise RuntimeError(f"Could not import xkcd_artist from {XKCD_SOURCE}: {exc}") from exc
    return _artist_fn


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "zero-comic-service",
        "backend": "onnx",
        "port": 8002,
        "output_dir": str(OUTPUT_DIR),
    }


@app.post("/generate", response_model=ComicResponse)
def generate(req: ComicRequest):
    req_id = req.request_id or f"zero-{uuid.uuid4().hex[:8]}"
    logger.info(f"Generating comic for [{req_id}]: {req.prompt[:60]}...")

    try:
        artist = get_artist()
        comic = artist(req.prompt, backend="onnx")

        # Extract PIL Image
        if hasattr(comic, "to_png"):
            raw_png = comic.to_png()
            pil_img = Image.open(io.BytesIO(raw_png)) if isinstance(raw_png, bytes) else raw_png
        elif hasattr(comic, "image"):
            pil_img = comic.image
        elif isinstance(comic, Image.Image):
            pil_img = comic
        else:
            raise RuntimeError(f"Unexpected result type from xkcd_artist: {type(comic)}")

        filename = f"{req_id}-{uuid.uuid4().hex[:6]}.png"
        filepath = OUTPUT_DIR / filename
        pil_img.save(filepath, format="PNG")
        width, height = pil_img.size

        logger.info(f"Generated comic saved: {filepath} ({width}x{height})")
        return ComicResponse(
            success=True,
            request_id=req_id,
            image_url=f"/images/{filename}",
            filename=filename,
            title=req.title,
            prompt=req.prompt,
            format="png",
            width=width,
            height=height,
        )
    except Exception as exc:
        logger.error(f"Generation error: {exc}", exc_info=True)
        return ComicResponse(
            success=False,
            request_id=req_id,
            title=req.title,
            prompt=req.prompt,
            error=str(exc),
        )


if __name__ == "__main__":
    print("[ZERO Comic Service] Starting server on http://0.0.0.0:8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002)

