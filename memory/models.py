from dataclasses import asdict, dataclass, field
from typing import Optional
from uuid import uuid4


@dataclass
class DocumentChunk:
    text: str
    embedding: list[float] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    doc_type: str = ""
    discipline: str = ""
    page: Optional[int] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("embedding", None)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentChunk":
        return cls(**data)
