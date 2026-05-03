from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


class BaseChunker(ABC):

    @abstractmethod
    def chunk(self, pdf_path: Path):
        """Générateur qui yield des Chunk un par un."""
        ...