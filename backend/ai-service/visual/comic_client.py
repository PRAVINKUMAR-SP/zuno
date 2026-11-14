"""HTTP client for the remote Ubuntu XKCD Comic Service."""

import logging
import socket
import time
from urllib.parse import urlparse
import uuid
import httpx

from config.settings import COMIC_SERVICE_URL, COMIC_ENABLED, COMIC_TIMEOUT

logger = logging.getLogger("comic-client")

_comic_health_cache = {"data": None, "ts": 0.0}


def check_comic_service_health() -> dict:
    """Check connectivity to remote comic service on Ubuntu with 10s caching."""
    if not COMIC_ENABLED:
        return {"status": "disabled", "ready": False, "url": COMIC_SERVICE_URL}

    now = time.time()
    if _comic_health_cache["data"] and (now - _comic_health_cache["ts"] < 10.0):
        return _comic_health_cache["data"]

    # Fast TCP probe first (0.25s) to avoid HTTP timeouts when port 8002 is down
    try:
        parsed = urlparse(COMIC_SERVICE_URL)
        host = parsed.hostname or "10.32.13.83"
        port = parsed.port or 8002
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.25)
            s.connect((host, port))
    except Exception:
        result = {
            "status": "offline",
            "ready": False,
            "url": COMIC_SERVICE_URL,
            "error": "port unreachable",
        }
        _comic_health_cache["data"] = result
        _comic_health_cache["ts"] = now
        return result

    # Socket connected, perform HTTP health check
    url = f"{COMIC_SERVICE_URL}/health"
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "status": "ok",
                    "ready": True,
                    "url": COMIC_SERVICE_URL,
                    "backend": data.get("backend", "onnx"),
                }
            else:
                result = {
                    "status": "degraded",
                    "ready": False,
                    "url": COMIC_SERVICE_URL,
                    "httpCode": resp.status_code,
                }
    except Exception as exc:
        result = {
            "status": "offline",
            "ready": False,
            "url": COMIC_SERVICE_URL,
            "error": str(exc),
        }

    _comic_health_cache["data"] = result
    _comic_health_cache["ts"] = now
    return result


def generate_comic(prompt: str, title: str = "Comic", request_id: str | None = None) -> dict | None:
    """Call the remote Ubuntu comic generator service synchronously or via threadpool."""
    if not COMIC_ENABLED:
        logger.info("Comic generation is disabled in settings.")
        return None

    req_id = request_id or f"zero-{uuid.uuid4().hex[:8]}"
    url = f"{COMIC_SERVICE_URL}/generate"
    payload = {
        "request_id": req_id,
        "prompt": prompt,
        "title": title,
        "panels": 4,
    }

    try:
        with httpx.Client(timeout=COMIC_TIMEOUT) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Comic service returned HTTP {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            if not data.get("success"):
                logger.warning(f"Comic generation failed on server: {data.get('error')}")
                return None

            raw_img_url = data.get("image_url", "")
            # Ensure URL is absolute so the client browser on Windows can load it
            if raw_img_url.startswith("/"):
                full_img_url = f"{COMIC_SERVICE_URL}{raw_img_url}"
            else:
                full_img_url = raw_img_url

            return {
                "success": True,
                "requestId": req_id,
                "title": title,
                "prompt": prompt,
                "imageUrl": full_img_url,
                "filename": data.get("filename"),
                "width": data.get("width"),
                "height": data.get("height"),
                "format": data.get("format", "png"),
            }
    except Exception as exc:
        logger.warning(f"Failed to reach comic service at {url}: {exc}")
        return None
