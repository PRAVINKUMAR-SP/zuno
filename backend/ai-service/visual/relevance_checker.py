"""Validates the structure and integrity of generated comic responses."""


def validate_comic_payload(comic_data: dict | None) -> bool:
    """Ensure comic metadata contains a valid image URL and format."""
    if not comic_data or not isinstance(comic_data, dict):
        return False

    if not comic_data.get("success"):
        return False

    image_url = comic_data.get("imageUrl") or ""
    if not image_url or not isinstance(image_url, str):
        return False

    if not (image_url.startswith("http://") or image_url.startswith("https://") or image_url.startswith("/")):
        return False

    return True

