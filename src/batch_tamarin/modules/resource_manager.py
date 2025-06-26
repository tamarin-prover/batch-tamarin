"""
Resource management system for tracking and scheduling ExecutableTask instances.

This module provides the ResourceManager class that handles global resource tracking,
intelligent task scheduling, and resource allocation/deallocation for parallel
Tamarin proof execution.
"""

import os
from typing import Dict, List

import psutil

from ..model.executable_task import ExecutableTask
from ..model.tamarin_recipe import TamarinRecipe
from ..utils.notifications import notification_manager


class ResourceManager:
    """
    Manages global resource allocation and intelligent task scheduling.

    This class tracks core and memory usage across all running tasks and implements
    an intelligent scheduling algorithm to maximize resource utilization while
    respecting global limits.
    """

    def __init__(self, recipe: TamarinRecipe) -> None:
        """
        Initialize the ResourceManager with a recipe containing resource limits.

        Args:
            recipe: TamarinRecipe object containing global configuration
        """
        self.recipe = recipe

        # Extract initial values from recipe config
        global_max_cores = recipe.config.global_max_cores
        global_max_memory = recipe.config.global_max_memory

        # Verify that global limits on cores are under system limits
        if cores := os.cpu_count():
            if global_max_cores > cores:
                notification_manager.warning(
                    f"[ResourceManager] Global max cores ({global_max_cores}) exceeds available CPU cores ({cores}). "
                )
                fallback = notification_manager.prompt_user(
                    "Do you want to fallback to maximum available cores?"
                )
                if fallback:
                    global_max_cores = cores
                    # Update the recipe's config object
                    self.recipe.config.global_max_cores = cores
                    notification_manager.info(
                        f"[ResourceManager] Falling back to {global_max_cores} cores."
                    )
                else:
                    notification_manager.info(
                        f"[ResourceManager] Using configured global max cores: {global_max_cores}."
                    )

        # Same goes for memory limits
        system_memory_gb = int(psutil.virtual_memory().total / (1024**3))  # type: ignore

        if global_max_memory > system_memory_gb:
            notification_manager.warning(
                f"[ResourceManager] Global max memory ({global_max_memory}GB) exceeds available system memory ({system_memory_gb}GB). "
            )
            fallback = notification_manager.prompt_user(
                "Do you want to fallback to maximum available memory?"
            )
            if fallback:
                global_max_memory = system_memory_gb
                # Update the recipe's config object
                self.recipe.config.global_max_memory = system_memory_gb
                notification_manager.info(
                    f"[ResourceManager] Falling back to {global_max_memory}GB memory."
                )
            else:
                notification_manager.info(
                    f"[ResourceManager] Using configured global max memory: {global_max_memory}GB."
                )

        # Store the final validated values as instance variables
        self.global_max_cores = global_max_cores
        self.global_max_memory = global_max_memory

        # Track current allocations
        self.allocated_cores = 0
        self.allocated_memory = 0

        # Track which tasks have resources allocated
        # Key: task identifier (task_name + tamarin_version_name)
        # Value: tuple of (cores, memory) allocated to that task
        self.task_allocations: Dict[str, tuple[int, int]] = {}

        notification_manager.debug(
            f"[ResourceManager] Initialized: {global_max_cores} cores, {global_max_memory}GB memory"
        )

    def can_schedule_task(self, task: ExecutableTask) -> bool:
        """
        Check if a task can be scheduled given current resource usage.

        Args:
            task: The ExecutableTask to check scheduling for

        Returns:
            True if enough cores and memory are available, False otherwise
        """
        available_cores = self.get_available_cores()
        available_memory = self.get_available_memory()

        can_schedule = (
            task.max_cores <= available_cores and task.max_memory <= available_memory
        )

        if not can_schedule:
            notification_manager.debug(
                f"[ResourceManager] Cannot schedule task {task.task_name}: "
                f"needs {task.max_cores} cores/{task.max_memory}GB, "
                f"available {available_cores} cores/{available_memory}GB"
            )

        return can_schedule

    def allocate_resources(self, task: ExecutableTask) -> bool:
        """
        Allocate resources to a task if possible.

        Args:
            task: The ExecutableTask to allocate resources for

        Returns:
            True if allocation successful, False if insufficient resources
        """
        task_id = task.task_name

        # Check if task already has resources allocated
        if task_id in self.task_allocations:
            notification_manager.error(
                f"[ResourceManager] Task {task_id} already has resources allocated"
            )
            return False

        # Check if allocation is possible
        if not self.can_schedule_task(task):
            return False

        # Allocate resources
        self.allocated_cores += task.max_cores
        self.allocated_memory += task.max_memory
        self.task_allocations[task_id] = (task.max_cores, task.max_memory)

        notification_manager.debug(
            f"[ResourceManager] Allocated resources to {task_id}: {task.max_cores} cores, {task.max_memory}GB. "
            f"Total allocated: {self.allocated_cores}/{self.global_max_cores} cores, "
            f"{self.allocated_memory}/{self.global_max_memory}GB memory"
        )

        return True

    def release_resources(self, task: ExecutableTask) -> None:
        """
        Release resources when a task completes.

        Args:
            task: The ExecutableTask to release resources for
        """
        task_id = task.task_name

        # Check if task has allocated resources
        if task_id not in self.task_allocations:
            notification_manager.error(
                f"[ResourceManager] Attempted to release resources for task {task_id} "
                f"that was not previously allocated"
            )
            return

        # Release resources
        cores, memory = self.task_allocations[task_id]
        self.allocated_cores -= cores
        self.allocated_memory -= memory
        del self.task_allocations[task_id]

        # Ensure allocations don't go negative due to edge cases
        self.allocated_cores = max(0, self.allocated_cores)
        self.allocated_memory = max(0, self.allocated_memory)

        notification_manager.debug(
            f"[ResourceManager] Released resources from {task_id}: {cores} cores, {memory}GB. "
            f"Total allocated: {self.allocated_cores}/{self.global_max_cores} cores, "
            f"{self.allocated_memory}/{self.global_max_memory}GB memory"
        )

    def get_next_schedulable_tasks(
        self, pending_tasks: List[ExecutableTask]
    ) -> List[ExecutableTask]:
        """
        Implement intelligent scheduling algorithm using greedy bin-packing.

        Sorts tasks by resource requirements (smallest first) and selects as many
        as possible that fit within current available resources.

        Args:
            pending_tasks: List of ExecutableTask instances waiting to be scheduled

        Returns:
            List of tasks that can be scheduled with current available resources
        """
        if not pending_tasks:
            return []

        # Sort tasks by total resource requirements (cores + memory) - smallest first
        sorted_tasks = sorted(
            pending_tasks, key=lambda task: task.max_cores + task.max_memory
        )

        schedulable_tasks: List[ExecutableTask] = []
        remaining_cores = self.get_available_cores()
        remaining_memory = self.get_available_memory()

        # Greedy bin-packing: select tasks that fit in remaining resources
        for task in sorted_tasks:
            if (
                task.max_cores <= remaining_cores
                and task.max_memory <= remaining_memory
            ):

                schedulable_tasks.append(task)
                remaining_cores -= task.max_cores
                remaining_memory -= task.max_memory

                notification_manager.debug(
                    f"[ResourceManager] Task {task.task_name} selected for scheduling: "
                    f"{task.max_cores} cores, {task.max_memory}GB. "
                    f"Remaining: {remaining_cores} cores, {remaining_memory}GB"
                )

        if schedulable_tasks:
            total_cores = sum(task.max_cores for task in schedulable_tasks)
            total_memory = sum(task.max_memory for task in schedulable_tasks)
            notification_manager.debug(
                f"[ResourceManager] Scheduling {len(schedulable_tasks)} tasks requiring "
                f"{total_cores} cores, {total_memory}GB total"
            )
        else:
            notification_manager.debug(
                "[ResourceManager] No tasks can be scheduled with current resources"
            )

        return schedulable_tasks

    def get_available_cores(self) -> int:
        """
        Get the number of cores currently available for allocation.

        Returns:
            Number of unallocated cores
        """
        return self.global_max_cores - self.allocated_cores

    def get_available_memory(self) -> int:
        """
        Get the amount of memory (in GB) currently available for allocation.

        Returns:
            Amount of unallocated memory in GB
        """
        return self.global_max_memory - self.allocated_memory

    def get_allocated_cores(self) -> int:
        """
        Get the number of cores currently allocated to tasks.

        Returns:
            Number of allocated cores
        """
        return self.allocated_cores

    def get_allocated_memory(self) -> int:
        """
        Get the amount of memory (in GB) currently allocated to tasks.

        Returns:
            Amount of allocated memory in GB
        """
        return self.allocated_memory
