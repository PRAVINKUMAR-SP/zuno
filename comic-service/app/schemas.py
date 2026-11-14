from typing import Optional
from pydantic import BaseModel, Field


class ComicRequest(BaseModel):
    request_id: Optional[str] = Field(default=None, description="Client tracking ID")
    prompt: str = Field(..., min_length=3, description="Comic visual description or render prompt")
    title: Optional[str] = Field(default="Comic", description="Comic title")
    panels: Optional[int] = Field(default=4, ge=1, le=6, description="Number of panels")


class ComicResponse(BaseModel):
    success: bool
    request_id: str
    image_url: Optional[str] = None
    filename: Optional[str] = None
    title: Optional[str] = None
    prompt: Optional[str] = None
    format: str = "png"
    width: Optional[int] = None
    height: Optional[int] = None
    error: Optional[str] = None

