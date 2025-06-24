#!/usr/bin/env python3
"""
Example demonstrating the singleton OutputManager usage.

This example shows how to use the singleton OutputManager to process Tamarin
execution results and create structured JSON outputs with proper directory organization.
"""

import json
import tempfile

# For this example, we'll define the necessary classes inline
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

# Note: In real usage, you would import from the installed package
# from tamarin_wrapper.modules.output_manager import output_manager
# from tamarin_wrapper.model.executable_task import TaskResult, TaskStatus, MemoryStats


class TaskStatus(Enum):
    """Status of a task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"


@dataclass
class MemoryStats:
    """Memory usage statistics for a task execution."""

    peak_memory_mb: float
    avg_memory_mb: float


@dataclass
class TaskResult:
    """Result of a completed task execution."""

    task_id: str
    status: TaskStatus
    return_code: int
    stdout: str
    stderr: str
    start_time: float
    end_time: float
    duration: float
    memory_stats: Optional[MemoryStats] = None


def create_sample_successful_result() -> TaskResult:
    """Create a sample successful TaskResult with realistic Tamarin output."""

    tamarin_output = """
maude tool: 'maude'
 checking version: 2.7.1
 checking installation: OK.

==============================================================================
summary of summaries:

analyzed: protocols/needham_schroeder_pk.spthy

  processing time: 4.23s

  secrecy (all-traces): verified (15 steps)
  authentication (all-traces): verified (12 steps)
  non_injective_agreement (all-traces): verified (8 steps)
  injective_agreement (all-traces): verified (10 steps)
  perfect_forward_secrecy (all-traces): verified (20 steps)
  attack_trace (exists-trace): falsified (5 steps)

==============================================================================
"""

    memory_stats = MemoryStats(peak_memory_mb=1024.5, avg_memory_mb=512.3)

    return TaskResult(
        task_id="needham_schroeder_pk_stable",
        status=TaskStatus.COMPLETED,
        return_code=0,
        stdout=tamarin_output,
        stderr="",
        start_time=1000.0,
        end_time=1004.23,
        duration=4.23,
        memory_stats=memory_stats,
    )


def create_sample_failed_result() -> TaskResult:
    """Create a sample failed TaskResult."""

    stderr_output = """
Error: Parse error in theory file
  --> protocols/broken_protocol.spthy:45:12
   |
45 |     rule BadRule
   |            ^^^^^^^ unexpected token
   |
   = expected: rule name or 'let' keyword

Error: Theory contains syntax errors and cannot be processed
Process terminated with exit code 1
"""

    memory_stats = MemoryStats(peak_memory_mb=128.0, avg_memory_mb=64.5)

    return TaskResult(
        task_id="broken_protocol_stable",
        status=TaskStatus.FAILED,
        return_code=1,
        stdout="",
        stderr=stderr_output,
        start_time=3000.0,
        end_time=3000.8,
        duration=0.8,
        memory_stats=memory_stats,
    )


def demonstrate_singleton_output_manager():
    """Demonstrate singleton OutputManager functionality."""

    print("=== Singleton OutputManager Usage Example ===\n")

    # Create a temporary directory for this example
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"Using temporary directory: {temp_path}\n")

        # In real usage with the singleton:
        # from tamarin_wrapper.modules.output_manager import output_manager

        # For this example, simulate the singleton behavior
        output_dir = temp_path / "tamarin_results"

        print("1. Singleton OutputManager Pattern:")
        print("   - Single global instance shared across the application")
        print("   - Initialized once with output directory")
        print("   - Automatically handles directory creation and user prompting")
        print("   - Available throughout the application lifetime\n")

        # Simulate directory creation (in real usage, output_manager.initialize() does this)
        success_dir = output_dir / "success"
        failed_dir = output_dir / "failed"
        models_dir = output_dir / "models"

        success_dir.mkdir(parents=True, exist_ok=True)
        failed_dir.mkdir(parents=True, exist_ok=True)
        models_dir.mkdir(parents=True, exist_ok=True)

        print("2. Directory structure created:")
        print(f"   - Base: {output_dir}")
        print(f"   - Success: {success_dir}")
        print(f"   - Failed: {failed_dir}")
        print(f"   - Models: {models_dir}\n")

        # Create sample task results
        successful_result = create_sample_successful_result()
        failed_result = create_sample_failed_result()

        print("3. Processing task results with Pydantic models:")
        print(
            f"   - Successful: {successful_result.task_id} ({successful_result.status.value})"
        )
        print(f"   - Failed: {failed_result.task_id} ({failed_result.status.value})\n")

        # Simulate the parsing and JSON creation using Pydantic models
        # (In real usage, output_manager.process_task_result() does this)

        # Successful task JSON (using Pydantic model structure)
        success_json = {
            "task_id": successful_result.task_id,
            "tamarin_timing": 4.23,
            "wrapper_measures": {
                "time": successful_result.duration,
                "avg_memory": (
                    successful_result.memory_stats.avg_memory_mb
                    if successful_result.memory_stats
                    else 0.0
                ),
                "peak_memory": (
                    successful_result.memory_stats.peak_memory_mb
                    if successful_result.memory_stats
                    else 0.0
                ),
            },
            "verified_lemma": {
                "secrecy": {"steps": 15, "analysis_type": "all-traces"},
                "authentication": {"steps": 12, "analysis_type": "all-traces"},
                "non_injective_agreement": {"steps": 8, "analysis_type": "all-traces"},
                "injective_agreement": {"steps": 10, "analysis_type": "all-traces"},
                "perfect_forward_secrecy": {"steps": 20, "analysis_type": "all-traces"},
            },
            "falsified_lemma": {
                "attack_trace": {"steps": 5, "analysis_type": "exists-trace"}
            },
            "unterminated_lemma": [],
            "warnings": [],
            "output_spthy": str(models_dir / f"{successful_result.task_id}.spthy"),
        }

        # Failed task JSON (using Pydantic model structure)
        failed_json = {
            "task_id": failed_result.task_id,
            "wrapper_measures": {
                "time": failed_result.duration,
                "avg_memory": (
                    failed_result.memory_stats.avg_memory_mb
                    if failed_result.memory_stats
                    else 0.0
                ),
                "peak_memory": (
                    failed_result.memory_stats.peak_memory_mb
                    if failed_result.memory_stats
                    else 0.0
                ),
            },
            "return_code": failed_result.return_code,
            "last_stderr_lines": (
                failed_result.stderr.strip().split("\n")[-10:]
                if failed_result.stderr.strip()
                else []
            ),
        }

        # Write JSON files
        success_json_path = success_dir / f"{successful_result.task_id}.json"
        failed_json_path = failed_dir / f"{failed_result.task_id}.json"

        with open(success_json_path, "w", encoding="utf-8") as f:
            json.dump(success_json, f, indent=2, ensure_ascii=False)

        with open(failed_json_path, "w", encoding="utf-8") as f:
            json.dump(failed_json, f, indent=2, ensure_ascii=False)

        print("4. Generated JSON files using Pydantic models:")
        print(f"   ✓ Success: {success_json_path}")
        print(f"   ✓ Failed: {failed_json_path}\n")

        print("5. Pydantic Model Benefits:")
        print("   - Automatic JSON serialization with model_dump_json()")
        print("   - Built-in validation and type checking")
        print("   - Easy schema generation and documentation")
        print("   - Consistent field descriptions and defaults")
        print("   - Better error handling for malformed data\n")

        print("6. Example Pydantic model usage in real code:")
        print(
            """
   # Successful task result
   result = SuccessfulTaskResult(
       task_id="my_task",
       tamarin_timing=4.23,
       wrapper_measures=WrapperMeasures(
           time=4.25,
           avg_memory=512.3,
           peak_memory=1024.5
       ),
       verified_lemma={
           "lemma1": LemmaResult(steps=15, analysis_type="all-traces")
       },
       output_spthy="/path/to/model.spthy"
   )

   # Serialize to JSON
   json_output = result.model_dump_json(indent=2)
        """
        )

        print("7. Generated JSON structure (Successful Task):")
        print(json.dumps(success_json, indent=2)[:500] + "...")

        print("\n8. Generated JSON structure (Failed Task):")
        print(json.dumps(failed_json, indent=2))

        print(f"\n=== Singleton OutputManager Example Complete ===")
        print("\nReal usage in the tamarin-wrapper:")
        print(
            "1. OutputManager is a singleton - one instance for the entire application"
        )
        print(
            "2. Initialize once: output_manager.initialize(Path('/output/directory'))"
        )
        print(
            "3. Use everywhere: output_manager.process_task_result(task_result, 'file.spthy')"
        )
        print("4. Automatic JSON creation with Pydantic models")
        print("5. Directory structure handled automatically")
        print("6. User prompting for existing directories")
        print("7. Graceful error handling throughout")


def demonstrate_integration_points():
    """Show how the singleton integrates with other components."""

    print("\n=== Integration Points ===\n")

    print("1. ConfigManager Integration:")
    print(
        "   - ConfigManager calls output_manager.initialize() during recipe processing"
    )
    print("   - Creates models/ directory for .spthy output files")
    print("   - Handles user prompting for directory cleanup")

    print("\n2. TaskManager Integration:")
    print("   - TaskManager automatically processes results via output_manager")
    print("   - No need to pass output_manager as parameter")
    print("   - Uses singleton pattern: output_manager.process_task_result()")

    print("\n3. No Manual Setup Required:")
    print("   - OutputManager is globally available")
    print("   - Initialize once, use everywhere")
    print("   - Consistent behavior across all components")

    print("\n4. Benefits of Singleton Pattern:")
    print("   - Single source of truth for output handling")
    print("   - No parameter passing between components")
    print("   - Consistent configuration throughout application")
    print("   - Easy to test and mock")


if __name__ == "__main__":
    demonstrate_singleton_output_manager()
    demonstrate_integration_points()
