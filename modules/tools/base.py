from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class Tool(ABC):
    """Base tool interface."""

    name: str = "tool"
    description: str = "generic tool"

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
