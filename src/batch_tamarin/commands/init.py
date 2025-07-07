"""
Interactive initialization command for batch-tamarin.

This module provides an interactive terminal for generating batch-tamarin
configuration files from spthy files.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from ..model.tamarin_recipe import GlobalConfig, TamarinRecipe, TamarinVersion, Task
from ..utils.system_resources import get_max_cpu_cores, get_max_memory_gb


class InitCommand:
    """Interactive initialization command for batch-tamarin."""

    def __init__(self):
        self.console = Console()

    def run(self, spthy_files: List[str], output_path: Optional[str] = None) -> None:
        """
        Run the interactive initialization process.

        Args:
            spthy_files: List of spthy file paths
            output_path: Optional output path for the generated config
        """
        self.console.print(
            Panel.fit(
                "[bold blue]Batch Tamarin Configuration Generator[/bold blue]",
                style="blue",
            )
        )

        # Validate spthy files exist
        validated_files = self._validate_spthy_files(spthy_files)
        if not validated_files:
            self.console.print("[red]No valid spthy files provided![/red]")
            return

        # Collect configuration interactively
        config = self._collect_global_config()
        tamarin_versions = self._collect_tamarin_versions()
        tasks = self._collect_tasks(validated_files, list(tamarin_versions.keys()))

        # Build the recipe
        recipe = TamarinRecipe(
            config=config, tamarin_versions=tamarin_versions, tasks=tasks
        )

        # Save or output
        if output_path:
            self._save_config(recipe, output_path)
        else:
            self._save_config(recipe, "recipe.json")

    def _validate_spthy_files(self, spthy_files: List[str]) -> List[Path]:
        """Validate that spthy files exist and are readable."""
        validated: List[Path] = []
        for file_path in spthy_files:
            path = Path(file_path)
            if not path.exists():
                self.console.print(f"[red]File not found:[/red] {file_path}")
                continue
            if not path.is_file():
                self.console.print(f"[red]Not a file:[/red] {file_path}")
                continue
            if not path.suffix.lower() == ".spthy":
                self.console.print(
                    f"[yellow]Warning:[/yellow] {file_path} doesn't have .spthy extension"
                )
            validated.append(path)
        return validated

    def _collect_global_config(self) -> GlobalConfig:
        """Collect global configuration settings interactively."""
        self.console.print("\n[bold]Global Configuration[/bold]")

        # Get system info for smart defaults
        system_cores = get_max_cpu_cores()
        system_memory = get_max_memory_gb()

        self.console.print(
            f"[dim]System detected: {system_cores} cores, {system_memory}GB RAM[/dim]"
        )

        # Max cores
        max_cores_input = Prompt.ask(
            f"Maximum CPU cores limit for all (concurrent) tasks [violet bold]{escape("[int, %, max]")}[/violet bold]",
            default="max",
            show_default=True,
        )
        max_cores = self._parse_resource_value(max_cores_input, system_cores, "cores")

        # Max memory
        max_memory_input = Prompt.ask(
            f"Maximum memory (GB) limit for all (concurrent) tasks [violet bold]{escape("[int, %, max]")}[/violet bold]",
            default="max",
            show_default=True,
        )
        max_memory = self._parse_resource_value(
            max_memory_input, system_memory, "memory"
        )

        # Default timeout
        default_timeout = IntPrompt.ask(
            "Default timeout (seconds) for each task", default=3600, show_default=True
        )

        # Output directory
        output_directory = Prompt.ask(
            "Results output directory", default="result", show_default=True
        )

        return GlobalConfig(
            global_max_cores=max_cores,
            global_max_memory=max_memory,
            default_timeout=default_timeout,
            output_directory=output_directory,
        )

    def _parse_resource_value(
        self, value: str, system_max: int, resource_type: str
    ) -> int | str:
        """Parse resource value input (max, percentage, or absolute)."""
        if value.lower() == "max":
            return "max"

        if value.endswith("%"):
            try:
                percentage = float(value[:-1])
                return max(1, int(system_max * percentage / 100))
            except ValueError:
                self.console.print(f"[red]Invalid percentage: {value}[/red]")
                return system_max

        try:
            return max(1, int(value))
        except ValueError:
            self.console.print(f"[red]Invalid {resource_type} value: {value}[/red]")
            return system_max

    def _collect_tamarin_versions(self) -> Dict[str, TamarinVersion]:
        """Collect Tamarin version configurations interactively."""
        self.console.print("\n[bold]Tamarin Versions[/bold]")

        versions: dict[str, TamarinVersion] = {}

        # First tamarin version
        first_path = Prompt.ask(
            "Give a path or a symbolic link to a tamarin-prover binary (leave default for system-installed-prover)",
            default="tamarin-prover",
            show_default=True,
        )
        first_alias = Prompt.ask(
            "What alias should this tamarin-prover be associated to ?",
            default="default",
            show_default=True,
        )

        versions[first_alias] = TamarinVersion(
            path=first_path, version=None, test_success=None
        )

        # Additional versions
        while Confirm.ask("Add another Tamarin version?", default=False):
            path = Prompt.ask("Path or symbolic link to tamarin-prover binary")
            if not path:
                self.console.print("[red]Path cannot be empty![/red]")
                continue

            alias = Prompt.ask("Linked alias for this version")
            if not alias:
                self.console.print("[red]Alias cannot be empty![/red]")
                continue

            if path in versions or alias in versions:
                self.console.print(
                    f"[red]Path '{path}' or alias '{alias}' already exists![/red]"
                )
                continue
            if not Path(path).exists():
                self.console.print(f"[red]Path '{path}' does not exist![/red]")
                continue

            versions[alias] = TamarinVersion(path=path, version=None, test_success=None)

        return versions

    def _collect_tasks(
        self, spthy_files: List[Path], tamarin_aliases: List[str]
    ) -> Dict[str, Task]:
        """Collect task configurations for each spthy file."""
        self.console.print("\n[bold]Tasks Configuration[/bold]")

        tasks: dict[str, Task] = {}

        for spthy_file in spthy_files:
            self.console.print(
                f"\n[bold cyan]Configuring task for:[/bold cyan] {spthy_file.name}"
            )

            # Task name
            default_task_name = spthy_file.stem
            task_name = Prompt.ask(
                "Task name", default=default_task_name, show_default=True
            )

            # Output file prefix
            output_prefix = Prompt.ask(
                "Result output file prefix", default=task_name, show_default=True
            )

            # Create task with all tamarin versions by default
            task = Task(
                theory_file=str(spthy_file),
                tamarin_versions=tamarin_aliases,
                output_file_prefix=output_prefix,
                lemmas=None,
                tamarin_options=None,
                preprocess_flags=None,
                resources=None,
            )

            tasks[task_name] = task

        return tasks

    def _save_config(self, recipe: TamarinRecipe, output_path: str) -> None:
        """Save the configuration to a file."""
        try:
            config_dict = recipe.model_dump(exclude_none=True)
            with open(output_path, "w") as f:
                json.dump(config_dict, f, indent=2)

            self.console.print(
                f"\n[green]Configuration saved to:[/green] {output_path}"
            )
        except Exception as e:
            self.console.print(f"[red]Error saving configuration:[/red] {e}")
