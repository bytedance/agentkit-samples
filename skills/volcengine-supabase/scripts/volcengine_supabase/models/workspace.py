from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Workspace(BaseModel):
    workspace_id: str
    workspace_name: str
    status: str
    region: str
    create_time: str
    engine_type: str
    engine_version: str


class Branch(BaseModel):
    branch_id: str
    branch_name: Optional[str] = None
    default: bool = False
    workspace_id: Optional[str] = None


class ApiKey(BaseModel):
    key: str
    name: str
    type: str
    create_time: Optional[str] = None
