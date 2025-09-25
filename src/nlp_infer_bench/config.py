"""Configuration dataclasses for the model conversion workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml


@dataclass
class ConversionConfig:
    """Options that control how models are converted."""

    frameworks: List[str]
    precision: str = "fp32"
    overwrite: bool = False
    local_cache: str = "artifacts/converted_models"


@dataclass
class ModelConfig:
    """Model metadata describing the source and intended task."""

    name: str
    task: str
    source: str
    revision: str = "main"
    extra_options: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExperimentConfig:
    """Top-level configuration for the conversion workflow."""

    experiment_name: str
    model_bucket: str
    model_registry: str
    conversion: ConversionConfig
    models: List[ModelConfig]

    @classmethod
    def from_path(cls, path: Path | str) -> "ExperimentConfig":
        with Path(path).open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict) -> "ExperimentConfig":
        conversion = ConversionConfig(**data["conversion"])
        models = [ModelConfig(**item) for item in data.get("models", [])]
        return cls(
            experiment_name=data["experiment_name"],
            model_bucket=data["model_bucket"],
            model_registry=data["model_registry"],
            conversion=conversion,
            models=models,
        )

    def to_dict(self) -> Dict:
        return {
            "experiment_name": self.experiment_name,
            "model_bucket": self.model_bucket,
            "model_registry": self.model_registry,
            "conversion": {
                "frameworks": list(self.conversion.frameworks),
                "precision": self.conversion.precision,
                "overwrite": self.conversion.overwrite,
                "local_cache": self.conversion.local_cache,
            },
            "models": [model.__dict__ for model in self.models],
        }


@dataclass
class RegistryEntry:
    """Record describing a converted model artifact."""

    model_name: str
    framework: str
    precision: str
    task: str
    revision: str
    local_path: str
    s3_uri: Optional[str] = None
    conversion_command: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ModelRegistry:
    """Collection of converted model artifacts."""

    artifacts: List[RegistryEntry] = field(default_factory=list)

    @classmethod
    def from_path(cls, path: Path | str) -> "ModelRegistry":
        registry_path = Path(path)
        if not registry_path.exists():
            return cls()
        with registry_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        entries = [RegistryEntry(**item) for item in data.get("artifacts", [])]
        return cls(artifacts=entries)

    def to_dict(self) -> Dict:
        return {"artifacts": [entry.__dict__ for entry in self.artifacts]}

    def save(self, path: Path | str) -> None:
        registry_path = Path(path)
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with registry_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(self.to_dict(), fh, sort_keys=False)

    def find(self, model_name: str, framework: str, precision: str) -> Optional[RegistryEntry]:
        for entry in self.artifacts:
            if (
                entry.model_name == model_name
                and entry.framework == framework
                and entry.precision == precision
            ):
                return entry
        return None

    def upsert(self, entry: RegistryEntry) -> None:
        existing = self.find(entry.model_name, entry.framework, entry.precision)
        if existing:
            self.artifacts.remove(existing)
        self.artifacts.append(entry)

    def filter(self, *, frameworks: Optional[Iterable[str]] = None) -> List[RegistryEntry]:
        if frameworks is None:
            return list(self.artifacts)
        return [entry for entry in self.artifacts if entry.framework in frameworks]
