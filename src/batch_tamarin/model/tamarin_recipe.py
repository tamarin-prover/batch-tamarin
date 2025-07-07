"""
Pydantic models for Tamarin Recipe configuration.

These models validate batch Tamarin configuration files according to
the tamarin-config-schema.json specification.
"""

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Lemma(BaseModel):
    """Individual lemma specification for proving."""

    model_config = ConfigDict(extra="forbid")

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
    resources: Optional["Resources"] = Field(
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

    model_config = ConfigDict(extra="forbid")

    max_cores: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum CPU cores for this task (inherited if not set)",
    )
    max_memory: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum memory in GB for this task (inherited if not set)",
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        description="Timeout in seconds (alias for task_timeout, used in lemma resources)",
    )


class TamarinVersion(BaseModel):
    """Individual tamarin version definition."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="File path to the Tamarin prover executable")
    version: Optional[str] = Field(
        None, description="Version identifier for this Tamarin prover"
    )
    test_success: Optional[bool] = Field(
        None, description="Whether this Tamarin executable passed connectivity tests"
    )


class Task(BaseModel):
    """Task configuration for Tamarin execution."""

    model_config = ConfigDict(extra="forbid")

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
    resources: Optional[Resources] = Field(
        None,
        description="Resource allocation for this task. If not specified, defaults to 4 cores, 16GB RAM, 3600s timeout",
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

    model_config = ConfigDict(extra="forbid")

    global_max_cores: int | str = Field(
        ...,
        description="Maximum number of CPU cores available system-wide for all tasks (integer or 'max' for system maximum)",
    )
    global_max_memory: int | str = Field(
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
    def validate_global_max_cores(cls, v: Union[int, str]) -> int | str:
        """Validate and resolve global_max_cores, converting 'max' to system maximum."""
        if isinstance(v, str) and v.lower() != "max":
            raise ValueError("String value must be 'max'")
        if isinstance(v, int) and v < 1:
            raise ValueError("global_max_cores must be at least 1")
        return v

    @field_validator("global_max_memory", mode="before")
    @classmethod
    def validate_global_max_memory(cls, v: Union[int, str]) -> int | str:
        """Validate and resolve global_max_memory, converting 'max' to system maximum."""
        if isinstance(v, str):
            if v.lower() == "max":
                return v
            elif v.endswith("%"):
                # Handle percentage case
                try:
                    percentage = int(v[:-1])
                    if not (1 <= percentage <= 100):
                        raise ValueError("Percentage must be between 1 and 100")
                    return v
                except ValueError:
                    raise ValueError(f"Invalid percentage format: {v}")
            else:
                raise ValueError("String value must be 'max' or a percentage")
        elif v < 1:
            raise ValueError("global_max_memory must be at least 1")
        return v


class TamarinRecipe(BaseModel):
    """Root configuration model for batch Tamarin."""

    model_config = ConfigDict(extra="forbid")

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
