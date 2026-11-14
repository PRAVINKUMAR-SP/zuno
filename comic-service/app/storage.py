import os
import uuid
from pathlib import Path
from PIL import Image

OUTPUT_DIR = Path(os.getenv("COMIC_OUTPUT_DIR", Path(__file__).resolve().parent.parent / "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_image_bytes(image_data: bytes | Image.Image, request_id: str | None = None) -> tuple[str, str, int, int]:
    req_slug = (request_id or "").replace("/", "_").replace("\\", "_")
    uid = uuid.uuid4().hex[:8]
    filename = f"zero-{req_slug}-{uid}.png" if req_slug else f"zero-{uid}.png"
    filepath = OUTPUT_DIR / filename

    if isinstance(image_data, Image.Image):
        image_data.save(filepath, format="PNG")
        width, height = image_data.size
    elif isinstance(image_data, bytes):
        with open(filepath, "wb") as f:
            f.write(image_data)
        with Image.open(filepath) as img:
            width, height = img.size
    else:
        raise ValueError(f"Unsupported image type: {type(image_data)}")

    return filename, str(filepath), width, height

