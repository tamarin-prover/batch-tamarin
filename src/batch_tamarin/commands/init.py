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

from ..model.tamarin_recipe import (
    GlobalConfig,
    Lemma,
    Resources,
    TamarinRecipe,
    TamarinVersion,
    Task,
)
from ..modules.lemma_parser import LemmaParser, LemmaParsingError
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
        # store for use in task-specific resource defaults
        self._global_config = config
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
            f"Maximum CPU cores limit for all (concurrent) tasks [violet bold]{escape("[int, max]")}[/violet bold]",
            default="max",
            show_default=True,
        )
        max_cores = self._parse_resource_value(max_cores_input, system_cores, "cores")

        # Max memory
        max_memory_input = Prompt.ask(
            f"Maximum memory (GB) limit for all (concurrent) tasks [violet bold]{escape("[int, int%, max]")}[/violet bold]",
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
                percentage = int(value[:-1])
                return f"{max(1, min(percentage, 100))}%"
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

            # Select Tamarin versions for this task
            selected_versions = self._select_tamarin_versions(
                tamarin_aliases, f"task '{task_name}'"
            )

            # Collect task-wide parameters
            tamarin_options = self._collect_tamarin_options(f"task '{task_name}'")
            preprocess_flags = self._collect_preprocess_flags(f"task '{task_name}'")
            resources = self._collect_resources(f"task '{task_name}'")
            lemmas = self._collect_lemmas(spthy_file, preprocess_flags, tamarin_aliases)

            # Create task with collected parameters
            task = Task(
                theory_file=str(spthy_file),
                tamarin_versions=selected_versions,
                output_file_prefix=output_prefix,
                resources=resources,
                tamarin_options=tamarin_options,
                preprocess_flags=preprocess_flags,
                lemmas=lemmas,
            )

            tasks[task_name] = task

        return tasks

    def _collect_tamarin_options(self, context: str) -> Optional[List[str]]:
        """Collect tamarin command-line options interactively."""
        if not Confirm.ask(
            f"Add tamarin command-line options for {context}?", default=False
        ):
            return None

        self.console.print(
            "[dim]Enter tamarin options separated by spaces or commas[/dim]"
        )
        self.console.print(
            "[dim]Example: '--heuristic=I --bound=5' or '--heuristic=I, --bound=5'[/dim]"
        )

        options_input = Prompt.ask("Tamarin options", default="")
        if not options_input.strip():
            return None

        # Split by comma or space, clean up whitespace
        if "," in options_input:
            options = [opt.strip() for opt in options_input.split(",") if opt.strip()]
        else:
            options = [opt.strip() for opt in options_input.split() if opt.strip()]

        # Basic validation - warn if options don't start with - or --
        for option in options:
            if not option.startswith("-"):
                self.console.print(
                    f"[yellow]Warning:[/yellow] '{option}' doesn't start with '-' or '--'"
                )

        return options if options else None

    def _collect_preprocess_flags(self, context: str) -> Optional[List[str]]:
        """Collect preprocessor flags interactively."""
        if not Confirm.ask(f"Add preprocessor flags for {context}?", default=False):
            return None

        self.console.print(
            "[dim]Enter preprocessor flags separated by spaces or commas[/dim]"
        )
        self.console.print("[dim]Example: 'DEBUG VERBOSE' or 'DEBUG, VERBOSE'[/dim]")
        self.console.print("[dim]These will be passed to Tamarin as -D=flag[/dim]")

        flags_input = Prompt.ask("Preprocessor flags", default="")
        if not flags_input.strip():
            return None

        # Split by comma or space, clean up whitespace
        if "," in flags_input:
            flags = [flag.strip() for flag in flags_input.split(",") if flag.strip()]
        else:
            flags = [flag.strip() for flag in flags_input.split() if flag.strip()]

        # Clean up flags - remove -D= prefix if user added it
        cleaned_flags: List[str] = []
        for flag in flags:
            if flag.startswith("-D="):
                cleaned_flags.append(flag[3:])
            elif flag.startswith("-D"):
                cleaned_flags.append(flag[2:])
            else:
                cleaned_flags.append(flag)

        return cleaned_flags if cleaned_flags else None

    def _collect_resources(self, context: str) -> Optional[Resources]:
        """Collect resource allocation settings interactively."""
        if not Confirm.ask(
            f"Configure custom resource allocation for {context}?", default=False
        ):
            return None

        self.console.print(
            "[dim]Configure resource limits for this specific task[/dim]"
        )
        # show global defaults for cores, memory, and timeout
        default_timeout = self._global_config.default_timeout
        self.console.print(
            f'[dim]Defaults : {{"cores": 4, "memory": 16, "timeout": {default_timeout}}} [/dim]'
        )

        # Collect max cores
        cores_input = Prompt.ask(
            "Override maximum CPU cores for this task [dim](empty for default)[/dim]",
            default="",
            show_default=False,
        )
        try:
            max_cores = (
                None if not cores_input else int(cores_input) if cores_input else None
            )
        except ValueError:
            self.console.print(
                f"[yellow]Warning:[/yellow] Invalid cores value '{cores_input}', using None"
            )
            max_cores = None

        # Collect max memory
        memory_input = Prompt.ask(
            "Override maximum memory (GB) for this task [dim](empty for default)[/dim]",
            default="",
            show_default=False,
        )
        try:
            max_memory = (
                None
                if not memory_input
                else int(memory_input) if memory_input else None
            )
        except ValueError:
            self.console.print(
                f"[yellow]Warning:[/yellow] Invalid memory value '{memory_input}', using None"
            )
            max_memory = None

        # Collect timeout
        timeout_input = Prompt.ask(
            "Override timeout (seconds) for this task [dim](empty for default)[/dim]",
            default="",
            show_default=False,
        )
        try:
            timeout = int(timeout_input) if timeout_input else None
        except ValueError:
            self.console.print(
                f"[yellow]Warning:[/yellow] Invalid timeout value '{timeout_input}', using None"
            )
            timeout = None

        # Only create Resources object if at least one value was provided
        if max_cores is not None or max_memory is not None or timeout is not None:
            return Resources(
                max_cores=max_cores,
                max_memory=max_memory,
                timeout=timeout,
            )

        return None

    def _collect_lemmas(
        self,
        spthy_file: Path,
        preprocess_flags: Optional[List[str]],
        tamarin_aliases: List[str],
    ) -> Optional[List[Lemma]]:
        """Collect lemmas for the task using interactive prefix-based selection with per-lemma configuration."""
        if not Confirm.ask("Configure specific lemmas for this task?", default=False):
            self.console.print("[dim]Using all lemmas (default behavior)[/dim]")
            return None

        # Parse lemmas from the file
        try:
            parser = LemmaParser(preprocess_flags)
            all_lemmas = parser.parse_lemmas_from_file(spthy_file)

            if not all_lemmas:
                self.console.print(
                    f"[yellow]No lemmas found in {spthy_file.name}[/yellow]"
                )
                return None

            self.console.print(
                f"[green]Found {len(all_lemmas)} lemmas in {spthy_file.name}[/green]"
            )

        except LemmaParsingError as e:
            self.console.print(
                f"[red]Error parsing lemmas from {spthy_file.name}: {e}[/red]"
            )
            return None

        # Interactive lemma selection with per-lemma configuration
        selected_lemmas: List[Lemma] = []

        self.console.print("[dim]Enter lemma names or prefixes one at a time[/dim]")
        self.console.print("[dim]Matching lemmas will be shown[/dim]")

        while True:
            # Interactive prefix input with immediate feedback
            prefix = self._get_lemma_prefix(all_lemmas)
            if not prefix:
                if not Confirm.ask("Add another lemma?", default=False):
                    break
                continue

            # Create lemma with per-lemma configuration
            lemma_obj = self._configure_individual_lemma(prefix, tamarin_aliases)
            selected_lemmas.append(lemma_obj)

            # Ask if user wants to add more
            if not Confirm.ask("Add another lemma?", default=False):
                break

        return selected_lemmas if selected_lemmas else None

    def _get_lemma_prefix(self, all_lemmas: List[str]) -> Optional[str]:
        """Get lemma prefix with immediate matching feedback."""
        while True:
            prefix = Prompt.ask("Lemma name or prefix", default="")
            if not prefix.strip():
                self.console.print("[yellow]Empty input, skipping[/yellow]")
                return None

            # Find matching lemmas (case-sensitive)
            matching_lemmas = [lemma for lemma in all_lemmas if prefix in lemma]

            if not matching_lemmas:
                self.console.print(f"[red]No lemmas match '{prefix}'[/red]")
                if not Confirm.ask("Try again?", default=True):
                    return None
                continue

            # Show matches immediately
            display_lemmas = matching_lemmas[:7]

            if len(matching_lemmas) == 1:
                self.console.print(
                    f"[green]✓[/green] '{prefix}' matches: {matching_lemmas[0]}"
                )
            else:
                self.console.print(
                    f"[green]✓[/green] '{prefix}' matches {len(matching_lemmas)} lemmas (showing first {len(display_lemmas)}):"
                )
                for match in display_lemmas:
                    self.console.print(f"    - {match}")

                if len(matching_lemmas) > 7:
                    self.console.print(f"    ... and {len(matching_lemmas) - 7} more")

            # Confirm this prefix
            if Confirm.ask(f"Use '{prefix}' as lemma prefix?", default=True):
                return prefix

    def _configure_individual_lemma(
        self, prefix: str, tamarin_aliases: List[str]
    ) -> Lemma:
        """Configure individual lemma settings (options, flags, resources, versions)."""
        self.console.print(f"\n[bold cyan]Configuring lemma '{prefix}'[/bold cyan]")

        # Ask if user wants to configure lemma-specific settings
        if not Confirm.ask(
            "Configure lemma-specific settings (versions, options, flags, resources)?",
            default=False,
        ):
            return Lemma(
                name=prefix,
                tamarin_versions=None,  # Will inherit from task
                tamarin_options=None,  # Will inherit from task
                preprocess_flags=None,  # Will inherit from task
                resources=None,  # Will inherit from task
            )

        # Collect lemma-specific tamarin versions (first)
        lemma_versions = self._select_tamarin_versions(
            tamarin_aliases, f"lemma '{prefix}'"
        )

        # Collect lemma-specific tamarin options
        lemma_options = self._collect_tamarin_options(f"lemma '{prefix}'")

        # Collect lemma-specific preprocessor flags
        lemma_flags = self._collect_preprocess_flags(f"lemma '{prefix}'")

        # Collect lemma-specific resources
        lemma_resources = self._collect_resources(f"lemma '{prefix}'")

        return Lemma(
            name=prefix,
            tamarin_versions=lemma_versions,
            tamarin_options=lemma_options,
            preprocess_flags=lemma_flags,
            resources=lemma_resources,
        )

    def _select_tamarin_versions(
        self, tamarin_aliases: List[str], context: str
    ) -> List[str]:
        """Select Tamarin versions"""
        if not tamarin_aliases:
            return []

        if len(tamarin_aliases) == 1:
            self.console.print(
                f"[dim]Only one Tamarin version available: '{tamarin_aliases[0]}' (auto-selected)[/dim]"
            )
            return tamarin_aliases

        self.console.print(f"\n[bold]Select Tamarin versions for {context}[/bold]")
        self.console.print("[dim]Enter version numbers or 'all' for all versions[/dim]")

        self.console.print(f"\n[bold] Available Tamarin versions: [/bold]")
        for i, alias in enumerate(tamarin_aliases, start=1):
            self.console.print(f"[bold]{i}.[/bold] {alias}")

        while True:
            selection_input = Prompt.ask(
                f"Select versions for {context}, comma or space separated [dim](e.g., '1,3' or '1 3' or 'all')[/dim]",
                default="all",
            ).strip()

            if selection_input.lower() == "all":
                self.console.print(
                    f"[green]✓[/green] Selected all {len(tamarin_aliases)} versions"
                )
                return tamarin_aliases

            # Parse selection
            try:
                if "," in selection_input:
                    indices = [
                        int(x.strip()) for x in selection_input.split(",") if x.strip()
                    ]
                else:
                    indices = [
                        int(x.strip()) for x in selection_input.split() if x.strip()
                    ]

                # Validate indices
                invalid_indices = [
                    i for i in indices if i < 1 or i > len(tamarin_aliases)
                ]
                if invalid_indices:
                    self.console.print(
                        f"[red]Invalid selection(s): {invalid_indices}. Please choose numbers 1-{len(tamarin_aliases)}[/red]"
                    )
                    continue

                # Check for duplicates
                if len(indices) != len(set(indices)):
                    self.console.print(
                        "[yellow]Warning: Duplicate selections removed[/yellow]"
                    )
                    indices = list(set(indices))

                if not indices:
                    self.console.print("[red]No valid selections made[/red]")
                    continue

                # Convert to aliases
                selected_versions = [
                    tamarin_aliases[i - 1] for i in sorted(set(indices))
                ]

                self.console.print(
                    f"[green]✓[/green] Selected {len(selected_versions)} version(s): {', '.join(selected_versions)}"
                )
                return selected_versions

            except ValueError:
                self.console.print(
                    f"[red]Invalid input: '{selection_input}'. Please enter numbers, 'all', or comma/space separated numbers[/red]"
                )
                continue

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
