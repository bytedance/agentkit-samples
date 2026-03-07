from typing import Optional, List
from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    format: str
    is_nullable: Optional[bool] = None
    is_unique: Optional[bool] = None
    default_value: Optional[str] = None


class Table(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    columns: List[Column] = []
    
    class Config:
        populate_by_name = True


class Migration(BaseModel):
    version: str
    name: str
