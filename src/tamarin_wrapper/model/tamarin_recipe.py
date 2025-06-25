"""
Pydantic models for Tamarin Recipe configuration.

These models validate Tamarin wrapper configuration files according to
the tamarin-config-schema.json specification.
"""

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.system_resources import resolve_max_value


class Lemma(BaseModel):
    """Individual lemma specification for proving."""

    name: str = Field(..., description="Name of the lemma to prove")
    tamarin_versions: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="List of Tamarin version aliases to run this lemma on. If not specified, inherits from task",
    )
    tamarin_options: Optional[List[str]] = Field(
        None,
        description="Additional command-line options to pass to Tamarin for this lemma. Overrides task-level options",
    )
    preprocess_flags: Optional[List[str]] = Field(
        None,
        description="Preprocessor flags to pass to Tamarin using -D=flag format for this lemma. Overrides task-level flags",
    )
    ressources: Optional["Resources"] = Field(
        None,
        description="Resource allocation for this lemma. If not specified, inherits from task",
    )

    @field_validator("tamarin_versions")
    @classmethod
    def tamarin_versions_unique(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure tamarin_versions are unique."""
        if v is not None and len(v) != len(set(v)):
            raise ValueError("tamarin_versions must contain unique items")
        return v


class Resources(BaseModel):
    """Resource allocation for tasks."""

    max_cores: Optional[int] = Field(
        default=4, ge=1, description="Maximum CPU cores for this task (default: 4)"
    )
    max_memory: Optional[int] = Field(
        default=8, ge=1, description="Maximum memory in GB for this task (default: 8)"
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        description="Timeout in seconds (alias for task_timeout, used in lemma resources)",
    )


class TamarinVersion(BaseModel):
    """Individual tamarin version definition."""

    path: str = Field(..., description="File path to the Tamarin prover executable")
    version: Optional[str] = Field(
        None, description="Version identifier for this Tamarin prover"
    )
    test_success: Optional[bool] = Field(
        None, description="Whether this Tamarin executable passed connectivity tests"
    )


class Task(BaseModel):
    """Task configuration for Tamarin execution."""

    theory_file: str = Field(
        ..., description="Path to the .spthy theory file to analyze"
    )
    tamarin_versions: List[str] = Field(
        ...,
        min_length=1,
        description="List of Tamarin version aliases to run this task on",
    )
    output_file_prefix: str = Field(
        ...,
        description="Output prefix for result, filled with _{lemma}_{tamarin-version}",
    )
    lemmas: Optional[List[Lemma]] = Field(
        None,
        description="List of lemmas to prove. If empty or omitted, all lemmas will be proved using --prove",
    )
    tamarin_options: Optional[List[str]] = Field(
        None, description="Additional command-line options to pass to Tamarin"
    )
    preprocess_flags: Optional[List[str]] = Field(
        None, description="Preprocessor flags to pass to Tamarin using -D=flag format"
    )
    ressources: Optional[Resources] = Field(
        None,
        description="Resource allocation for this task. If not specified, defaults to 4 cores, 8GB RAM, 3600s timeout",
    )

    @field_validator("tamarin_versions")
    @classmethod
    def tamarin_versions_unique(cls, v: List[str]) -> List[str]:
        """Ensure tamarin_versions are unique."""
        if len(v) != len(set(v)):
            raise ValueError("tamarin_versions must contain unique items")
        return v


class GlobalConfig(BaseModel):
    """Global configuration settings."""

    global_max_cores: int = Field(
        ...,
        description="Maximum number of CPU cores available system-wide for all tasks (integer or 'max' for system maximum)",
    )
    global_max_memory: int = Field(
        ...,
        description="Maximum memory in GB available system-wide for all tasks (integer or 'max' for system maximum)",
    )
    default_timeout: int = Field(
        ...,
        ge=1,
        description="Default timeout in seconds for tasks (used when task doesn't specify resources)",
    )
    output_directory: str = Field(
        ..., description="Base directory path for all output files"
    )

    @field_validator("global_max_cores", mode="before")
    @classmethod
    def validate_global_max_cores(cls, v: Union[int, str]) -> int:
        """Validate and resolve global_max_cores, converting 'max' to system maximum."""
        if isinstance(v, str) and v.lower() != "max":
            raise ValueError("String value must be 'max'")
        resolved = resolve_max_value(v, "cores")
        if resolved < 1:
            raise ValueError("global_max_cores must be at least 1")
        return resolved

    @field_validator("global_max_memory", mode="before")
    @classmethod
    def validate_global_max_memory(cls, v: Union[int, str]) -> int:
        """Validate and resolve global_max_memory, converting 'max' to system maximum."""
        if isinstance(v, str) and v.lower() != "max":
            raise ValueError("String value must be 'max'")
        resolved = resolve_max_value(v, "memory")
        if resolved < 1:
            raise ValueError("global_max_memory must be at least 1")
        return resolved


class TamarinRecipe(BaseModel):
    """Root configuration model for Tamarin wrapper."""

    config: GlobalConfig = Field(..., description="Global configuration settings")
    tamarin_versions: Dict[str, TamarinVersion] = Field(
        ..., description="Named aliases for different Tamarin prover executables"
    )
    tasks: Dict[str, Task] = Field(
        ..., description="Named tasks, each defining a Tamarin execution configuration"
    )

    @model_validator(mode="after")
    def validate_name_patterns(self) -> "TamarinRecipe":
        """Validate that keys match the required pattern: ^[a-zA-Z][a-zA-Z0-9_-]*$"""
        import re

        pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

        # Validate tamarin_versions keys
        for key in self.tamarin_versions.keys():
            if not pattern.match(key):
                raise ValueError(
                    f'Tamarin version key "{key}" must start with a letter and contain only letters, numbers, underscores, and hyphens'
                )

        # Validate tasks keys
        for key in self.tasks.keys():
            if not pattern.match(key):
                raise ValueError(
                    f'Task key "{key}" must start with a letter and contain only letters, numbers, underscores, and hyphens'
                )

        return self

    def get_task_resources(self, task_name: str) -> Resources:
        """
        Get the effective resources for a task, applying defaults from global config.

        Args:
            task_name: Name of the task to get resources for

        Returns:
            Resources object with defaults applied

        Raises:
            KeyError: If task_name doesn't exist
        """
        task = self.tasks[task_name]
        if task.ressources is None:
            # Apply defaults: 4 cores, 8GB memory, default_timeout from global config
            return Resources(
                max_cores=4, max_memory=8, timeout=self.config.default_timeout
            )

        # Apply global default_timeout if timeout is not specified
        resources = task.ressources.model_copy()
        if resources.timeout is None:
            resources.timeout = self.config.default_timeout

        return resources
