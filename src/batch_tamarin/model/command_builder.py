"""Command builder interfaces and implementations for ExecutableTask.

This module provides an abstract interface for building commands from ExecutableTasks,
with separate implementations for local and Docker execution modes.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .executable_task import ExecutableTask


class CommandBuilder(ABC):
    """Abstract interface for building commands from ExecutableTasks."""

    @abstractmethod
    async def build(self, task: "ExecutableTask") -> List[str]:
        """
        Build a command from an ExecutableTask.

        Args:
            task: ExecutableTask to build command for

        Returns:
            List of command components ready for execution
        """


class LocalCommandBuilder(CommandBuilder):
    """Command builder for local execution using tamarin-prover executable."""

    async def build(self, task: "ExecutableTask") -> List[str]:
        """Build command for local execution."""
        if not task.tamarin_executable:
            raise RuntimeError("Local execution requires tamarin_executable")

        # Build base tamarin command
        base_command = [str(task.tamarin_executable)]

        # Add Haskell RTS flags for performance limiting
        base_command.extend(["+RTS", f"-N{task.max_cores}", "-RTS"])

        # Add theory file
        base_command.append(str(task.theory_file))

        if task.lemma:
            # Prove specific lemma
            base_command.append(f"--prove={task.lemma}")

        # Add tamarin options if provided
        if task.tamarin_options:
            base_command.extend(task.tamarin_options)

        # Add preprocessor flags with -D= prefix if provided
        if task.preprocess_flags:
            for flag in task.preprocess_flags:
                base_command.append(f"-D={flag}")

        # Add trace output parameters
        base_command.append(f"--output-json={task.traces_dir}/{task.task_name}.json")
        base_command.append(f"--output-dot={task.traces_dir}/{task.task_name}.dot")

        # Add output file
        base_command.append(f"--output={task.output_file}")

        # Apply compatibility filtering based on tamarin version
        from ..utils.compatibility_filter import compatibility_filter

        filtered_command = await compatibility_filter(
            base_command, task.tamarin_executable
        )
        return filtered_command


class DockerCommandBuilder(CommandBuilder):
    """Command builder for Docker execution."""

    async def build(self, task: "ExecutableTask") -> List[str]:
        """Build command for Docker execution."""
        if not task.docker_image:
            raise RuntimeError("Docker execution requires docker_image")

        # Build base tamarin command (without executable path)
        base_command = ["tamarin-prover"]

        # Add Haskell RTS flags for performance limiting
        base_command.extend(["+RTS", f"-N{task.max_cores}", "-RTS"])

        # Add theory file (absolute path)
        base_command.append(str(task.theory_file.absolute()))

        if task.lemma:
            # Prove specific lemma
            base_command.append(f"--prove={task.lemma}")

        # Add tamarin options if provided
        if task.tamarin_options:
            base_command.extend(task.tamarin_options)

        # Add preprocessor flags with -D= prefix if provided
        if task.preprocess_flags:
            for flag in task.preprocess_flags:
                base_command.append(f"-D={flag}")

        # Add trace output parameters (absolute paths)
        base_command.append(
            f"--output-json={task.traces_dir.absolute()}/{task.task_name}.json"
        )
        base_command.append(
            f"--output-dot={task.traces_dir.absolute()}/{task.task_name}.dot"
        )

        # Add output file (absolute path)
        base_command.append(f"--output={task.output_file.absolute()}")

        # Apply compatibility filtering based on tamarin version
        from ..utils.compatibility_filter import compatibility_filter_with_version

        # Use version string if available, otherwise return command as-is
        filtered_command = compatibility_filter_with_version(
            base_command, task.tamarin_version or ""
        )

        return filtered_command


def create_command_builder(task: "ExecutableTask") -> CommandBuilder:
    """
    Factory function to create the appropriate command builder for a task.

    Args:
        task: ExecutableTask to create builder for

    Returns:
        CommandBuilder instance appropriate for the task's execution mode
    """
    if task.docker_image:
        return DockerCommandBuilder()
    elif task.tamarin_executable:
        return LocalCommandBuilder()
    else:
        raise ValueError("Task must have either docker_image or tamarin_executable")
