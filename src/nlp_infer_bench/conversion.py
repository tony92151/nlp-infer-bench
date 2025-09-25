"""Model conversion pipeline."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from huggingface_hub import snapshot_download

from .config import ExperimentConfig, ModelConfig, ModelRegistry, RegistryEntry
from .s3_utils import upload_directory

LOGGER = logging.getLogger(__name__)


@dataclass
class ConversionTask:
    model: ModelConfig
    framework: str
    precision: str
    output_dir: Path


def _sanitize(name: str) -> str:
    return name.replace("/", "-")


def _run_command(command: List[str], env: Dict[str, str] | None = None) -> None:
    LOGGER.info("Running command: %s", " ".join(command))
    subprocess.run(command, check=True, env=env)


def _convert_transformers(task: ConversionTask) -> None:
    LOGGER.info("Downloading %s using Hugging Face snapshot", task.model.name)
    snapshot_download(
        repo_id=task.model.name,
        revision=task.model.revision,
        local_dir=task.output_dir,
        local_dir_use_symlinks=False,
    )


def _convert_onnx(task: ConversionTask) -> None:
    command = [
        "optimum-cli",
        "export",
        "onnx",
        "--model",
        task.model.name,
        str(task.output_dir),
        "--task",
        task.model.task,
        "--revision",
        task.model.revision,
    ]
    _run_command(command)


def _convert_openvino(task: ConversionTask) -> None:
    command = [
        "optimum-cli",
        "export",
        "openvino",
        "--model",
        task.model.name,
        str(task.output_dir),
        "--task",
        task.model.task,
        "--revision",
        task.model.revision,
    ]
    _run_command(command)


_CONVERTERS = {
    "transformers": _convert_transformers,
    "onnx-runtime": _convert_onnx,
    "openvino": _convert_openvino,
}


class Converter:
    """Coordinates the conversion of configured models."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self.registry_path = Path(config.model_registry)
        self.registry = ModelRegistry.from_path(self.registry_path)

    def plan_tasks(self) -> List[ConversionTask]:
        tasks: List[ConversionTask] = []
        cache_base = Path(self.config.conversion.local_cache)
        for model in self.config.models:
            model_dir = cache_base / _sanitize(model.name)
            for framework in self.config.conversion.frameworks:
                framework_dir = model_dir / framework / self.config.conversion.precision
                tasks.append(
                    ConversionTask(
                        model=model,
                        framework=framework,
                        precision=self.config.conversion.precision,
                        output_dir=framework_dir,
                    )
                )
        return tasks

    def run(self, *, upload: bool = True) -> None:
        tasks = self.plan_tasks()
        cache_base = Path(self.config.conversion.local_cache)
        cache_base.mkdir(parents=True, exist_ok=True)

        for task in tasks:
            registry_entry = self.registry.find(
                task.model.name, task.framework, task.precision
            )
            if registry_entry and not self.config.conversion.overwrite:
                LOGGER.info(
                    "Skipping %s - %s (already converted)",
                    task.model.name,
                    task.framework,
                )
                continue

            if task.output_dir.exists() and self.config.conversion.overwrite:
                LOGGER.info("Removing previous conversion at %s", task.output_dir)
                shutil.rmtree(task.output_dir)

            task.output_dir.mkdir(parents=True, exist_ok=True)
            LOGGER.info(
                "Converting %s to %s (precision=%s)",
                task.model.name,
                task.framework,
                task.precision,
            )
            converter = _CONVERTERS.get(task.framework)
            if converter is None:
                raise ValueError(f"Unsupported framework: {task.framework}")
            converter(task)

            s3_uri = None
            if upload:
                bucket_uri = self._make_model_bucket_prefix(task)
                s3_uri = upload_directory(task.output_dir, bucket_uri)

            registry_entry = RegistryEntry(
                model_name=task.model.name,
                framework=task.framework,
                precision=task.precision,
                task=task.model.task,
                revision=task.model.revision,
                local_path=str(task.output_dir),
                s3_uri=s3_uri,
            )
            self.registry.upsert(registry_entry)
            self.registry.save(self.registry_path)

    def _make_model_bucket_prefix(self, task: ConversionTask) -> str:
        sanitized = _sanitize(task.model.name)
        prefix = f"{self.config.model_bucket.strip('/')}/{sanitized}/{task.framework}/{task.precision}"
        if prefix.startswith("s3://"):
            prefix = prefix[len("s3://") :]
        return prefix


def convert_models(config_path: str, *, upload: bool = True) -> None:
    config = ExperimentConfig.from_path(config_path)
    converter = Converter(config)
    converter.run(upload=upload)
