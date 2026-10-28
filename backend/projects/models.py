from pydantic import BaseModel, Field, field_validator

ALLOWED_CATEGORIES = [
    "product_advertisement",
    "brand_identity",
    "social_media",
    "music_promotion",
    "album_artwork",
    "ecommerce",
    "editorial_poster",
    "concept_art",
    "cinematic_scene",
    "video_advertisement",
    "general",
]


def _clean_text(value: str, max_len: int) -> str:
    return " ".join(value.split())[:max_len]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="general")
    brief: str = Field(default="", max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        stripped = _clean_text(v, 120)
        if not stripped:
            raise ValueError("Project name must not be empty")
        return stripped

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str) -> str:
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(ALLOWED_CATEGORIES)}")
        return v

    @field_validator("description", "brief", mode="before")
    @classmethod
    def clean_long_text(cls, v: str) -> str:
        return _clean_text(str(v), 8000)

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if not v:
            return []
        cleaned = []
        for item in v:
            tag = _clean_text(str(item), 40)
            if tag:
                cleaned.append(tag)
        return cleaned


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = None
    brief: str | None = Field(default=None, max_length=8000)
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = _clean_text(v, 120)
        if not stripped:
            raise ValueError("Project name must not be empty")
        return stripped

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(ALLOWED_CATEGORIES)}")
        return v

    @field_validator("description", "brief", mode="before")
    @classmethod
    def clean_long_text(cls, v):
        if v is None:
            return None
        return _clean_text(str(v), 8000)

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if v is None:
            return None
        cleaned = []
        for item in v:
            tag = _clean_text(str(item), 40)
            if tag:
                cleaned.append(tag)
        return cleaned


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    category: str
    brief: str
    tags: list[str]
    asset_count: int = 0
    created_at: str
    updated_at: str
