from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class EdgeFunction(BaseModel):
    id: str
    slug: str
    name: str
    status: str
    version: int
    created_at: str
    updated_at: str
    verify_jwt: bool
    entrypoint_path: str
    runtime_config: Optional[str] = None
    runtime: Optional[str] = None


class EdgeFunctionFile(BaseModel):
    name: str
    content: str


class EdgeFunctionDeployment(BaseModel):
    name: str
    entrypoint_path: str = "index.ts"
    verify_jwt: bool = True
    import_map_path: Optional[str] = None
    files: List[EdgeFunctionFile]
