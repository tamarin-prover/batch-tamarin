"""Generators for Tamarin output processing."""

from .failed_generator import FailedTaskGenerator
from .processed_generator import ProcessedOutputGenerator

__all__ = ["FailedTaskGenerator", "ProcessedOutputGenerator"]
