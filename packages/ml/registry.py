"""Model registry with versioning."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("model_registry")


class ModelStage(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    version: str = "1.0.0"
    model_type: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    stage: ModelStage = ModelStage.DEVELOPMENT
    artifact_path: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ModelRegistry:
    def __init__(self):
        self._models: dict[str, list[ModelVersion]] = {}

    def register(self, name: str, version: str, model_type: str, parameters: dict[str, Any] | None = None) -> str:
        mv = ModelVersion(name=name, version=version, model_type=model_type, parameters=parameters or {})
        self._models.setdefault(name, []).append(mv)
        logger.info("model_registered", name=name, version=version)
        return mv.id

    def promote(self, model_id: str, stage: ModelStage) -> bool:
        for versions in self._models.values():
            for v in versions:
                if v.id == model_id:
                    v.stage = stage
                    logger.info("model_promoted", name=v.name, stage=stage.value)
                    return True
        return False

    def get_production(self, name: str) -> ModelVersion | None:
        versions = self._models.get(name, [])
        for v in versions:
            if v.stage == ModelStage.PRODUCTION:
                return v
        return None

    def list(self, name: str | None = None) -> list[dict]:
        if name:
            versions = self._models.get(name, [])
        else:
            versions = [v for vv in self._models.values() for v in vv]
        return [
            {"id": v.id, "name": v.name, "version": v.version, "stage": v.stage.value, "metrics": v.metrics}
            for v in versions
        ]


registry = ModelRegistry()
