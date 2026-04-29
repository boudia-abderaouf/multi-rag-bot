from abc import ABC, abstractmethod
from pathlib import Path
 
 
class BaseLoader(ABC):
    """
    Interface commune à tous les loaders.
    Chaque loader reçoit la config d'un document (depuis documents.yaml)
    et retourne le Path local vers le fichier prêt à être traité.
    """
 
    def __init__(self, doc_config: dict):
        self.doc_id = doc_config["id"]
        self.doc_name = doc_config["name"]
 
    @abstractmethod
    def load(self) -> Path:
        """
        Charge le document et retourne son chemin local.
        Doit être idempotent : appeler load() deux fois ne doit pas causer de problème.
        """
        ...