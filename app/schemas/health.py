from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    rag_version: int
    rag_indexed_chunks: int
    ollama: str
    models: dict[str, str] = Field(default_factory=dict)
