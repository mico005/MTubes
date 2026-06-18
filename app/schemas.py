from pydantic import BaseModel


class TrackRequest(BaseModel):
    id: str
    title: str
    uploader: str | None = "Unknown"
    thumbnail: str | None = None
    duration: int | None = 0


class TrackResponse(BaseModel):
    id: str
    title: str
    uploader: str | None
    thumbnail: str | None
    duration: int | None

    class Config:
        from_attributes = True
