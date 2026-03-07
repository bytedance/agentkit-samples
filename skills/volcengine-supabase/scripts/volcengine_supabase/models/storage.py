from typing import Optional
from pydantic import BaseModel


class StorageBucket(BaseModel):
    id: str
    name: str
    owner: Optional[str] = None
    public: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class StorageConfig(BaseModel):
    fileSizeLimit: int
    totalFileSizeLimit: Optional[int] = None
