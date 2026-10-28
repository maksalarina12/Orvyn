from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class AssetOut(BaseModel):
    id: str
    project_id: str | None
    path: str
    filename: str
    file_type: str
    mime_type: str
    width: int | None
    height: int | None
    file_size: int
    source: str
    prompt: str | None
    negative_prompt: str | None
    model_name: str | None
    seed: int | None
    backend: str | None
    revision_of: str | None
    notes: str
    is_favorite: bool
    created_at: str
    updated_at: str


class AssetUpdate(BaseModel):
    project_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_favorite: bool | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, v):
        if v is None:
            return None
        return " ".join(str(v).split())[:2000]


class AssetDeleteOptions(BaseModel):
    confirm: bool = False
    delete_file: bool = False


def read_image_dimensions(path: Path) -> tuple[int, int] | None:
    from PIL import Image

    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None
