import logging
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.generator import generate_comic_png
from app.schemas import ComicRequest, ComicResponse
from app.storage import OUTPUT_DIR, save_image_bytes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("comic-service")

app = FastAPI(title="ZERO XKCD Comic Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated PNG images directly over HTTP
app.mount("/images", StaticFiles(directory=str(OUTPUT_DIR)), name="images")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "zero-comic-service",
        "backend": "onnx",
        "output_dir": str(OUTPUT_DIR),
    }


@app.get("/version")
def version():
    return {
        "version": "1.0.0",
        "model": "xkcd-artist",
        "backend": "onnx",
    }


@app.post("/generate", response_model=ComicResponse)
def generate_comic(req: ComicRequest):
    request_id = req.request_id or f"zero-{uuid.uuid4().hex[:8]}"
    logger.info(f"Generating comic for [{request_id}]: {req.prompt[:60]}...")
    
    try:
        pil_img = generate_comic_png(req.prompt, backend="onnx")
        filename, filepath, width, height = save_image_bytes(pil_img, request_id)
        
        return ComicResponse(
            success=True,
            request_id=request_id,
            image_url=f"/images/{filename}",
            filename=filename,
            title=req.title,
            prompt=req.prompt,
            format="png",
            width=width,
            height=height,
        )
    except Exception as exc:
        logger.error(f"Comic generation failed for [{request_id}]: {exc}", exc_info=True)
        return ComicResponse(
            success=False,
            request_id=request_id,
            title=req.title,
            prompt=req.prompt,
            error=str(exc),
        )

