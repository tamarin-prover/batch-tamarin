# Implementation Plan for Tamarin Wrapper Output Enhancements

## Overview

This implementation plan provides a focused approach to enhance the tamarin-wrapper project with output processing, memory monitoring, and reporting capabilities. The plan is structured around 4 core tasks that build upon the existing modular architecture.

---

## File Structure & Organization

### New Directory Structure
Refactor :
Move existing modules into `src/tamarin_wrapper/modules/cmd_builder` and create new modules for output processing and reporting.

```
src/tamarin_wrapper/
├── modules/
│   ├── cmd_output/                           # NEW: Output processing module
│   │   ├── __init__.py
│   │   ├── capture.py                    # OutputCapture component
│   │   ├── processor.py                  # TamarinOutputProcessor
│   │   ├── storage.py                    # StorageManager
│   │   └── error_analyzer.py             # ErrorAnalyzer
│   └── reporting/                        # NEW: Report generation module
│       ├── __init__.py
│       ├── generator.py                  # ReportGenerator
│       ├── formats/                      # Report format handlers
│       │   ├── __init__.py
│       │   ├── html_format.py
│       │   ├── latex_format.py
│       │   └── markdown_format.py
│       └── templates/                    # Report templates
│           ├── html_template.html
│           ├── latex_template.tex
│           └── markdown_template.md
└── model/
    ├── output_models.py              # NEW: Extended data models
    ├── reporting_config.py           # NEW: Report-specific models
    └── output_config.py              # NEW: Output configuration models
```

### Modified Existing Files

- [`src/tamarin_wrapper/model/executable_task.py`](src/tamarin_wrapper/model/executable_task.py) - Extend TaskResult
- [`src/tamarin_wrapper/modules/process_manager.py`](src/tamarin_wrapper/modules/process_manager.py) - Add output capture
- [`src/tamarin_wrapper/modules/task_manager.py`](src/tamarin_wrapper/modules/task_manager.py) - Integrate output processing
- [`src/tamarin_wrapper/runner.py`](src/tamarin_wrapper/runner.py) - Add memory monitoring
- [`pyproject.toml`](pyproject.toml) - Add new dependencies
- [`tamarin-config-schema.json`](tamarin-config-schema.json) - Extend configuration schema

---

## Task Breakdown

### Task 1: Memory Monitoring

Track memory usage during task execution and include statistics in execution summaries.

#### Subtask 1.1: Add Memory Monitoring to TaskResult

Extend the [`TaskResult`](src/tamarin_wrapper/model/executable_task.py:1) class with memory tracking capabilities.

**Data Model Extension:**
Extend the existing [`TaskResult`](src/tamarin_wrapper/model/executable_task.py:122) class:
```python
@dataclass
class TaskResult:
    # ... existing fields from executable_task.py ...
    memory_stats: Optional[MemoryStats] = None

@dataclass
class MemoryStats:
    """Memory usage statistics for a task execution."""
    peak_memory_mb: float
    avg_memory_mb: float
```
Add `MemoryStats` to [`src/tamarin_wrapper/model/executable_task.py`](src/tamarin_wrapper/model/executable_task.py).
**Implementation Approach:**
- Use `psutil` library for cross-platform memory monitoring
- Integrate memory monitoring in [`ProcessManager.run_command()`](src/tamarin_wrapper/modules/process_manager.py:1)
- Sample memory usage every 1 seconds during task execution
- Store MemoryStats in TaskResult for summary reporting

#### Subtask 1.2: Add Memory Statistics to Execution Summary

Enhance [`TaskRunner.execute_all_tasks()`](src/tamarin_wrapper/runner.py:1) to display memory statistics.

**Implementation Approach:**
- Modify summary generation in runner to include memory metrics
- Add memory formatting utilities in [`utils/notifications.py`](src/tamarin_wrapper/utils/notifications.py:1)
- Display peak and avg memory per task and total peak across all tasks

---

### Task 2: Output Processing

Create a comprehensive output processing system that captures, stores, and processes Tamarin execution output.

#### Subtask 2.1: Create Output Models and Configuration

**Data Models (`src/tamarin_wrapper/model/output_models.py`):**
```python
@dataclass
class CapturedOutput:
    """Raw output captured from task execution."""
    task_id: str
    raw_stdout: str
    raw_stderr: str
    output_file_path: Path
    timestamp: datetime
    compression_used: bool

@dataclass
class LemmaResult:
    """Individual lemma verification result."""
    name: str
    status: str  # "verified", "falsified", "analysis_incomplete"
    time_ms: Optional[int]
    steps: Optional[int]

@dataclass
class ParsedTamarinOutput:
    """Structured Tamarin output after parsing."""
    lemma_results: Dict[str, LemmaResult]
    total_time_ms: int
    total_steps: int
    warnings: List[str]
    errors: List[str]
    # Reuse existing ExecutionSummary from executable_task.py for consistency
```

**Configuration Model (`src/tamarin_wrapper/model/output_config.py`):**
```python
class OutputConfig(BaseModel):
    capture_enabled: bool = True
    compression_threshold_kb: int = 100
    store_raw_output: bool = True
    max_output_size_mb: int = 50
```

#### Subtask 2.2: Create Capture Component

**Implementation Approach (`src/tamarin_wrapper/modules/cmd_output/capture.py`):**
- Extend [`ProcessManager.run_command()`](src/tamarin_wrapper/modules/process_manager.py:1) to capture all output
- Store unprocessed output as `{task_id}_{timestamp}.spthy` files
- For failed tasks, create `failed_task.json` with error details and context
- Use LZ4 compression for outputs larger than threshold
- Implement streaming capture to handle very large outputs without memory issues

**Storage Strategy (`src/tamarin_wrapper/modules/cmd_output/storage.py`):**
```python
class OutputStorage:
    """Handles storage and retrieval of task outputs."""
    def store_raw_output(self, task_id: str, output: str, stderr: str) -> Path
    def store_failed_task(self, task_id: str, task_result: TaskResult) -> Path
    def retrieve_output(self, task_id: str) -> Optional[CapturedOutput]
    # Uses existing TaskResult from executable_task.py for failed task info
```

#### Subtask 2.3: Process Output to Result JSON

**Implementation Approach (`src/tamarin_wrapper/modules/cmd_output/processor.py`):**
- Create `TamarinOutputProcessor` class that uses regex patterns to parse Tamarin output
- Extract lemma verification results, timing information, and proof statistics
- Generate structured `result.json` files in output directory
- Handle common Tamarin output variations and edge cases
- Integrate with [`TaskManager.run_executable_task()`](src/tamarin_wrapper/modules/task_manager.py:1) for automatic processing

**Parser Patterns:**
```python
TAMARIN_PATTERNS = {
    'lemma_start': r'==== (\w+) ====',
    'lemma_result': r'(verified|falsified|analysis incomplete) \((.+?)\)',
    'timing': r'(\d+)ms',
    'proof_steps': r'(\d+) steps'
}
```


---

### Task 3: Error Analysis

Develop an intelligent error analysis system that helps users understand and resolve task failures.

#### Subtask 3.1: Read and Analyze Failed Tasks

**Error Analysis Model (`src/tamarin_wrapper/model/output_models.py`):**
```python
class ErrorType(Enum):
    """Types of errors that can occur during task execution."""
    TIMEOUT = "timeout"
    MEMORY_EXHAUSTED = "memory"
    SYNTAX_ERROR = "syntax"
    PROOF_FAILURE = "proof_failure"
    SYSTEM_ERROR = "system"

@dataclass
class ErrorAnalysis:
    """Analysis of a failed task execution."""
    error_type: ErrorType
    description: str
    context_lines: List[str]
    suggested_fixes: List[str]
```

**Error Analyzer (`src/tamarin_wrapper/modules/cmd_output/error_analyzer.py`):**
```python
class ErrorAnalyzer:
    def analyze_failed_task(self, failed_task_path: Path) -> ErrorAnalysis:
        # Parse failed_task.json and apply pattern matching
```

**Implementation Approach:**
- Automatically scan output directory for `failed_task.json` files after execution
- Use regex patterns to categorize errors from stderr and return codes
- Extract relevant context (line numbers, error messages, stack traces)
- Integrate with [`TaskRunner`](src/tamarin_wrapper/runner.py:1) to run analysis automatically

**Error Pattern Matching:**
```python
ERROR_PATTERNS = {
    ErrorType.TIMEOUT: [r'timeout', r'killed.*signal.*15'],
    ErrorType.MEMORY_EXHAUSTED: [r'out of memory', r'oom-killer'],
    ErrorType.SYNTAX_ERROR: [r'parse error', r'syntax error'],
    ErrorType.PROOF_FAILURE: [r'analysis incomplete', r'falsified']
}
```

---

### Task 4: Report Generation

Build a flexible report generation system that creates comprehensive execution reports in multiple formats.

#### Subtask 4.1: Create Report Configuration and Templates

**Report Configuration (`src/tamarin_wrapper/model/reporting_config.py`):**
```python
class ReportFormat(Enum):
    """Supported report output formats."""
    HTML = "html"
    MARKDOWN = "md"
    LATEX = "tex"

class ReportConfig(BaseModel):
    """Configuration for report generation."""
    formats: List[ReportFormat] = [ReportFormat.HTML]
    include_memory_charts: bool = True
    include_raw_output: bool = False
    template_dir: Optional[List[Path]] = None  # By default, use built-in templates. The list is in the order of the earlier given formats.

@dataclass
class MemoryAnalysis:
    """Aggregated memory analysis across all tasks."""
    total_peak_memory_mb: float
    average_memory_mb: float
    high_memory_tasks: List[str]  # task_ids

@dataclass
class ErrorSummary:
    """Summary of errors across execution."""
    error_counts_by_type: Dict[ErrorType, int]
    total_failed_tasks: int

class ReportData(BaseModel):
    """Aggregated data for report generation."""
    # Reuse existing ExecutionSummary and TaskResult from executable_task.py
    execution_summary: ExecutionSummary  # From executable_task.py
    task_results: List[TaskResult]  # From executable_task.py
    memory_analysis: MemoryAnalysis
    error_summary: ErrorSummary
```

**Template Structure:**
- HTML template with embedded CSS and JavaScript for interactive charts
- Markdown template for documentation/README generation
- LaTeX template for academic paper appendices
- Use Jinja2 templating with common data model across all formats

#### Subtask 4.2: Create Main Report Generator

**Implementation Approach (`src/tamarin_wrapper/modules/reporting/generator.py`):**
- Create `ReportGenerator` class that reads all `result.json` files from output directory
- Aggregate data into `ReportData` model with summary statistics
- Call format-specific renderers based on configuration
- Integrate with [`TaskRunner`](src/tamarin_wrapper/runner.py:1) to auto-generate reports after execution

**Report Generation Flow:**
```python
class ReportGenerator:
    def generate_reports(self, output_dir: Path, config: ReportConfig) -> List[Path]:
        # 1. Collect all result.json files
        # 2. Aggregate into ReportData
        # 3. Generate each requested format
        # 4. Return list of generated report files
```

#### Subtask 4.3: Create Template-Specific Handlers

**HTML Format (`src/tamarin_wrapper/modules/reporting/formats/html_format.py`):**
- Use Plotly.js for interactive memory usage charts and execution timelines
- Responsive CSS grid layout for task results
- Collapsible sections for detailed output and error analysis
- Include search/filter functionality for large task sets

**Markdown Format (`src/tamarin_wrapper/modules/reporting/formats/markdown_format.py`):**
- Generate tables for task summaries and statistics
- Include code blocks for error details and configurations
- Create hierarchical structure with proper heading levels
- Support GitHub-flavored markdown extensions

**LaTeX Format (`src/tamarin_wrapper/modules/reporting/formats/latex_format.py`):**
- Generate publication-ready tables and figures
- Use proper scientific notation for performance metrics
- Include bibliography support for Tamarin references
- Support both standalone documents and includable sections

---
### Task 5: User Interaction for Rerun Recipes

#### Subtask 5.1: User Interaction for Rerun Recipes

**Implementation Approach:**
- After error analysis, prompt user with interactive CLI using `typer` prompts
- Generate `rerun_failed.json` based on error type and user choices
- Support batch operations for multiple failed tasks with similar errors
- Validate rerun configuration against schema before saving

**Rerun Recipe Model (`src/tamarin_wrapper/model/output_models.py`):**
```python
@dataclass
class TaskModifications:
    """Modifications to apply when rerunning failed tasks."""
    timeout_multiplier: float = 1.0
    memory_limit_gb: Optional[int] = None # Default to tamarin_recipe max memory limit
    additional_args: List[str] = field(default_factory=list)

@dataclass
class RerunRecipe:
    """Recipe for rerunning failed tasks with modifications."""
    task_ids: List[str]
    modifications: TaskModifications
    retry_count: int = 1
```

#### Subtask 5.2: Suggest Error-Specific Modifications

**Implementation Approach:**
- Create suggestion engine that maps error types to recommended fixes
- Use heuristics based on error context (e.g., if timeout on large file, suggest higher timeout)
- Integrate with configuration management to suggest config changes
- Display suggestions in CLI with numbered options for user selection

**Suggestion Engine (`src/tamarin_wrapper/modules/cmd_output/error_analyzer.py`):**
```python
@dataclass
class Suggestion:
    """A suggested fix for an error."""
    description: str
    confidence: float  # 0.0 - 1.0
    config_changes: Dict[str, Any]
    explanation: str

class SuggestionEngine:
    def get_suggestions(self, error: ErrorAnalysis, task: ExecutableTask) -> List[Suggestion]:
        # Return contextual suggestions based on error type and task characteristics
        # Uses existing ExecutableTask from executable_task.py
```

---

## Dependencies and Configuration Updates

**Required additions to [`pyproject.toml`](pyproject.toml):**
```toml
dependencies = [
    # Existing dependencies...
    "psutil>=5.9.0",       # Memory monitoring
    "jinja2>=3.1.0",       # Template rendering
    "plotly>=5.17.0",      # Interactive charts (HTML reports)
    "lz4>=4.3.0",          # Fast compression
]
```

**Configuration schema updates in [`tamarin-config-schema.json`](tamarin-config-schema.json):**
```json
{
  "properties": {
    "output": {
      "type": "object",
      "properties": {
        "capture_enabled": {"type": "boolean", "default": true},
        "compression_threshold_kb": {"type": "integer", "default": 100}
      }
    },
    "reporting": {
      "type": "object",
      "properties": {
        "formats": {"type": "array", "items": {"type": "string"}, "default": ["html"]},
        "include_memory_charts": {"type": "boolean", "default": true}
      }
    }
  }
}
```

**Configuration schema updates in [`tamarin-config-schema.json`](tamarin-config-schema.json):**
- Add output processing configuration section
- Include memory monitoring settings
- Define report generation options
- Specify error analysis parameters
