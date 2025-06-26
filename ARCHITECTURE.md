# Batch Tamarin Architecture

## Project Overview

The batch Tamarin is a Python-based orchestration tool that enables batch execution of Tamarin Prover protocol verification tasks. It provides a structured approach to running multiple protocol analyses across different Tamarin versions with comprehensive resource management, progress tracking, and result processing.

The system is designed around a modular architecture with clear separation of concerns, allowing for efficient parallel execution while maintaining resource constraints and providing detailed progress reporting.

## Project Structure

```
batch-tamarin/
├── src/batch_tamarin/                    # Main package source
│   ├── __init__.py                         # Package initialization
│   ├── main.py                             # CLI entry point and application coordinator
│   ├── runner.py                           # High-level task execution orchestration
│   │
│   ├── model/                              # Data models and type definitions
│   │   ├── __init__.py
│   │   ├── tamarin_recipe.py              # Pydantic models for JSON configuration
│   │   └── executable_task.py             # Runtime task representation and enums
│   │
│   ├── modules/                            # Core functionality modules
│   │   ├── __init__.py
│   │   ├── config_manager.py              # JSON loading, validation, transformation
│   │   ├── resource_manager.py            # Global resource tracking and scheduling
│   │   ├── task_manager.py                # Individual task execution with monitoring
│   │   ├── process_manager.py             # Low-level process management and monitoring
│   │   ├── output_manager.py              # Tamarin output parsing and result generation
│   │   └── tamarin_test_cmd.py            # Tamarin binary validation utilities
│   │
│   └── utils/                              # Utility functions and helpers
│       ├── __init__.py
│       ├── notifications.py               # User communication and logging system
│       └── system_resources.py            # System resource detection and validation
│
├── examples/                               # Example configuration files
│   ├── example_config.json                # Basic configuration example
│   └── wpa2.json                          # WPA2 protocol analysis example
│
├── scripts/                                # Development and utility scripts
│
├── pyproject.toml                          # Python project configuration
├── requirements.txt                        # Python development environment
├── tamarin-config-schema.json              # JSON schema for configuration validation
├── README.md                               # User documentation
├── RECIPE_GUIDE.md                         # Configuration guide
├── ARCHITECTURE.md                         # This file - system architecture
└── flake.nix                               # Nix development environment
```

## High-Level System Architecture

The system follows a layered architecture with clear data flow and responsibility separation:

```mermaid
graph TB
    subgraph "Entry Layer"
        CLI[CLI Entry Point<br/>main.py]
    end

    subgraph "Configuration Layer"
        CM[Config Manager]
        JSON[JSON Recipe File]
        PM[Pydantic Models]
        ET[ExecutableTask Objects]
    end

    subgraph "Execution Layer"
        TR[Task Runner]
        RM[Resource Manager]
        TM[Task Manager]
    end

    subgraph "Process Layer"
        PROC[Process Manager]
        TP[Tamarin Processes]
    end

    subgraph "Output Layer"
        OM[Output Manager]
        RESULTS[JSON Results]
        MODELS[SPTHY Models]
    end

    CLI --> CM
    JSON --> CM
    CM --> PM
    PM --> ET
    ET --> TR
    RM <--> TR
    TR --> TM
    TM --> PROC
    PROC --> TP
    TP --> OM
    OM --> RESULTS
    TP --> MODELS
```

### Architecture Layers Explained

1. **Entry Layer**: Handles CLI argument parsing and initiates the execution pipeline
2. **Configuration Layer**: Validates JSON recipes and transforms them into executable objects
3. **Execution Layer**: Orchestrates parallel task execution with resource management
4. **Process Layer**: Manages individual Tamarin processes and system monitoring
5. **Output Layer**: Processes results and generates structured output files

## Component Integration Flow

The following sequence diagram shows how components interact during a typical execution:

```mermaid
sequenceDiagram
    participant User
    participant CLI as CLI Entry
    participant CM as Config Manager
    participant TR as Task Runner
    participant RM as Resource Manager
    participant TM as Task Manager
    participant PM as Process Manager
    participant OM as Output Manager

    User->>CLI: batch-tamarin recipe.json
    CLI->>CM: load_json_recipe()
    CM->>CM: Validate with Pydantic
    CM->>TR: ExecutableTask list
    TR->>RM: Initialize resources
    RM->>RM: Validate system limits

    loop For each task pool
        TR->>RM: Check available resources
        RM->>TR: Schedulable tasks
        TR->>TM: Execute tasks
        TM->>PM: Run command
        PM->>PM: Monitor process
        PM->>TM: Task result
        TM->>OM: Process output
        OM->>OM: Generate JSON
        TM->>TR: Task completed
        TR->>RM: Release resources
    end

    TR->>User: Execution summary
```

### Integration Flow Details

- **Initialization Phase**: CLI loads configuration, validates it, and creates executable tasks
- **Resource Planning**: Resource manager validates system constraints and prepares scheduling
- **Execution Phase**: Tasks are scheduled based on available resources and executed in parallel
- **Monitoring Phase**: Each task is monitored for memory usage, timeouts, and completion
- **Output Phase**: Results are processed and saved in structured format

## Data Model Architecture

The system uses Pydantic models for configuration validation and runtime objects for execution:

```mermaid
classDiagram
    class TamarinRecipe {
        +GlobalConfig config
        +Dict~str,TamarinVersion~ tamarin_versions
        +Dict~str,Task~ tasks
        +validate_name_patterns()
        +get_task_resources()
    }

    class GlobalConfig {
        +int global_max_cores
        +int global_max_memory
        +int default_timeout
        +str output_directory
    }

    class TamarinVersion {
        +str path
        +str version
        +bool test_success
    }

    class Task {
        +str theory_file
        +List~str~ tamarin_versions
        +str output_file_prefix
        +List~Lemma~ lemmas
        +List~str~ tamarin_options
        +List~str~ preprocess_flags
        +Resources resources
    }

    class Lemma {
        +str name
        +List~str~ tamarin_versions
        +List~str~ tamarin_options
        +List~str~ preprocess_flags
        +Resources resources
    }

    class Resources {
        +int max_cores
        +int max_memory
        +int timeout
    }

    class ExecutableTask {
        +str task_name
        +str tamarin_version_name
        +Path tamarin_executable
        +Path theory_file
        +Path output_file
        +str lemma
        +List~str~ tamarin_options
        +List~str~ preprocess_flags
        +int max_cores
        +int max_memory
        +int task_timeout
        +to_command()
    }

    TamarinRecipe --> GlobalConfig
    TamarinRecipe --> TamarinVersion
    TamarinRecipe --> Task
    Task --> Lemma
    Task --> Resources
    Lemma --> Resources
    Task --> ExecutableTask : transforms to
```

## Core Components

### 1. CLI Entry Point (`main.py`)

The main entry point provides a Typer-based CLI interface and orchestrates the entire execution pipeline.

**Key Responsibilities:**
- Parse command-line arguments (config file, debug mode, revalidation flags)
- Initialize the notification system and debug settings
- Handle version display and help information
**Key Functions:**
- `main()`: Primary CLI entry point with argument parsing
- `process_config_file()`: Async orchestrator for the entire workflow
- `cli()`: Entry point for pip-installed command

### 2. Configuration Manager (`modules/config_manager.py`)

Handles all aspects of configuration loading, validation, and transformation into executable objects.

**Key Responsibilities:**
- Load and parse JSON configuration files
- Validate configuration against Pydantic models
- Transform recipes into ExecutableTask objects
- Handle Tamarin binary validation (with `modules/tamarin_test_cmd`)
- Provide detailed error reporting for configuration issues

**Key Methods:**
- `load_json_recipe()`: Loads and validates JSON recipe files
- `recipe_to_executable_tasks()`: Converts recipes to ExecutableTask objects
- Task expansion logic for handling multiple versions and lemmas

### 3. Task Runner (`runner.py`)

High-level orchestration component that manages the entire task execution lifecycle.

**Key Responsibilities:**
- Coordinate parallel task execution with resource constraints
- Handle graceful shutdown and signal management
- Provide real-time progress updates and reporting
- Manage task pools and execution queues
- Handle error conditions and cleanup procedures

**Key Methods:**
- `execute_all_tasks()`: Main execution coordinator
- `_execute_task_pool()`: Parallel task execution with resource management
- `_start_schedulable_tasks()`: Intelligent task scheduling
- `_handle_completed_tasks()`: Process task completion and cleanup

## Task Execution State Machine

Tasks progress through well-defined states during their lifecycle:

```mermaid
stateDiagram-v2
    [*] --> PENDING: Task Created

    PENDING --> RUNNING: Resources Available
    PENDING --> PENDING: Waiting for Resources

    RUNNING --> COMPLETED: Success
    RUNNING --> FAILED: Process Error
    RUNNING --> TIMEOUT: Time Limit Exceeded
    RUNNING --> MEMORY_LIMIT_EXCEEDED: Memory Limit Hit

    COMPLETED --> [*]: Output Processed
    FAILED --> [*]: Error Logged
    TIMEOUT --> [*]: Timeout Logged
    MEMORY_LIMIT_EXCEEDED --> [*]: Memory Error Logged

    note right of RUNNING
        Process Manager monitors:
        - Memory usage
        - Time elapsed
        - Process status
    end note
```

### State Transitions

- **PENDING**: Task is queued and waiting for sufficient resources
- **RUNNING**: Task is actively executing with process monitoring
- **COMPLETED**: Task finished successfully with results processed
- **FAILED**: Task encountered an error during execution
- **TIMEOUT**: Task exceeded its time limit and was terminated
- **MEMORY_LIMIT_EXCEEDED**: Task exceeded memory limits and was terminated

## Resource Management System

The resource management system ensures efficient utilization while respecting system constraints:

```mermaid
flowchart TD
    START([Start]) --> INIT[Initialize Global Limits]
    INIT --> CHECK_SYSTEM{System Limits OK?}
    CHECK_SYSTEM -->|No| FALLBACK[Apply System Fallback]
    CHECK_SYSTEM -->|Yes| READY[Resource Pool Ready]
    FALLBACK --> READY

    READY --> SCHEDULE_LOOP{Tasks Pending?}
    SCHEDULE_LOOP -->|No| END([Complete])
    SCHEDULE_LOOP -->|Yes| CHECK_RESOURCES{Resources Available?}

    CHECK_RESOURCES -->|No| WAIT[Wait for Resources]
    CHECK_RESOURCES -->|Yes| ALLOCATE[Allocate Resources]

    WAIT --> MONITOR_RUNNING[Monitor Running Tasks]
    ALLOCATE --> START_TASK[Start Task]
    START_TASK --> MONITOR_RUNNING

    MONITOR_RUNNING --> TASK_DONE{Task Completed?}
    TASK_DONE -->|No| MONITOR_RUNNING
    TASK_DONE -->|Yes| RELEASE[Release Resources]
    RELEASE --> SCHEDULE_LOOP
```

### Resource Manager (`modules/resource_manager.py`)

**Key Responsibilities:**
- Track global CPU and memory usage across all running tasks
- Implement intelligent scheduling algorithms
- Enforce global resource limits with automatic fallbacks
- Provide resource allocation and deallocation tracking
- Validate resource configurations against system capacity

**Scheduling Algorithm:**
- Prioritizes tasks that can efficiently utilize available resources
- Prevents resource over-allocation through predictive scheduling
- Balances CPU and memory constraints for optimal throughput

### 4. Task Manager (`modules/task_manager.py`)

Manages individual task execution with comprehensive monitoring and progress tracking.

**Key Responsibilities:**
- Execute ExecutableTask objects with full lifecycle tracking
- Monitor task status changes and collect execution statistics
- Generate comprehensive TaskResult objects
- Integrate with ProcessManager for actual process execution
- Provide progress reporting capabilities

**Task Lifecycle Management:**
- Status tracking from creation to completion
- Timing and memory usage collection
- Error handling and result processing
- Integration with output management

### 5. Process Manager (`modules/process_manager.py`)

Low-level process execution and monitoring component with advanced resource tracking.

**Key Responsibilities:**
- Launch and manage Tamarin processes asynchronously
- Monitor memory usage in real-time and enforce limits
- Handle process timeouts and graceful termination
- Collect stdout/stderr output comprehensively
- Track detailed process execution statistics

**Process Monitoring Features:**
- Continuous memory usage tracking with psutil
- Automatic termination when resource limits are exceeded
- Comprehensive process statistics collection
- Orphaned process cleanup and resource reclamation

## Configuration Processing Pipeline

The configuration system transforms JSON files into executable tasks through a comprehensive validation pipeline:

```mermaid
flowchart
  subgraph "Input"
      JSON_FILE[JSON Recipe File]
  end

  subgraph "Validation"
      LOAD[Load JSON]
      VALIDATE[Pydantic Validation]
      CHECK_PATHS[Check File Paths]
      VERIFY_TAMARIN[Verify Tamarin Binaries]
  end

  subgraph "Transformation"
      CREATE_RECIPE[Create TamarinRecipe]
      EXPAND_TASKS[Expand Task Combinations]
      CREATE_EXECUTABLE[Create ExecutableTask Objects]
  end

  subgraph "Output"
      TASK_LIST[List of ExecutableTask]
  end

  JSON_FILE --> LOAD
  LOAD --> VALIDATE
  VALIDATE --> CHECK_PATHS
  CHECK_PATHS --> VERIFY_TAMARIN
  VERIFY_TAMARIN --> CREATE_RECIPE
  CREATE_RECIPE --> EXPAND_TASKS
  EXPAND_TASKS --> CREATE_EXECUTABLE
  CREATE_EXECUTABLE --> TASK_LIST

  VALIDATE -->|Error| ERROR1[Validation Error]
  CHECK_PATHS -->|Error| ERROR2[Path Error]
  VERIFY_TAMARIN -->|Error| ERROR3[Binary Error]
```

### Configuration Processing Steps

1. **JSON Loading**: Parse JSON file with error handling
2. **Pydantic Validation**: Validate structure and types against models
3. **Path Verification**: Check that all file paths exist and are accessible
4. **Binary Validation**: Optionally verify Tamarin executable integrity
5. **Task Expansion**: Create individual ExecutableTask objects for each combination
6. **Resource Validation**: Ensure resource requirements are feasible

## Output Processing System

The output management system processes Tamarin results and generates structured output:

```mermaid
flowchart TD
    TAMARIN_OUTPUT[Tamarin Process Output] --> PARSE_STDOUT[Parse STDOUT]
    TAMARIN_OUTPUT --> PARSE_STDERR[Parse STDERR]

    PARSE_STDOUT --> EXTRACT_TIMING[Extract Timing Info]
    PARSE_STDOUT --> EXTRACT_LEMMAS[Extract Lemma Results]
    PARSE_STDOUT --> EXTRACT_WARNINGS[Extract Warnings]
    PARSE_STDERR --> EXTRACT_ERRORS[Extract Error Messages]

    EXTRACT_TIMING --> BUILD_SUCCESS{Task Successful?}
    EXTRACT_LEMMAS --> BUILD_SUCCESS
    EXTRACT_WARNINGS --> BUILD_SUCCESS
    TAMARIN_OUTPUT_MODEL[Tamarin outputs a model] --> BUILD_SUCCESS
    EXTRACT_ERRORS --> BUILD_SUCCESS

    BUILD_SUCCESS -->|Yes| SUCCESS_JSON[Create Success JSON]
    BUILD_SUCCESS -->|No| FAILED_JSON[Create Failed JSON]

    SUCCESS_JSON --> SAVE_SUCCESS[Save to success/]
    FAILED_JSON --> SAVE_FAILED[Save to failed/]
    TAMARIN_OUTPUT_MODEL --> SAVE_MODEL[Save to models/]
```

### Output Manager (`modules/output_manager.py`)

**Key Responsibilities:**
- Parse Tamarin execution output using regex patterns
- Extract timing information, lemma results, and warning messages
- Generate structured JSON results for both successful and failed tasks
- Manage output directory structure and file organization
- Handle error conditions and provide diagnostic information

**Output Processing Features:**
- Comprehensive output parsing with detailed result extraction
- Structured JSON format for consistent result reporting
- Automatic file organization in success/failed/models directories
- Rich error reporting with context and troubleshooting information

## File System Output Structure

The system organizes output files in a structured directory hierarchy:

```mermaid
graph TD
    subgraph "Output Directory Structure"
        OUTPUT_DIR[output_directory/]

        subgraph "Success Results"
            SUCCESS_DIR[success/]
            SUCCESS_JSON[task_lemma_version.json<br/>Contains: verified lemmas, timing,<br/>warnings, wrapper measurements]
        end

        subgraph "Failed Results"
            FAILED_DIR[failed/]
            FAILED_JSON[task_lemma_version.json<br/>Contains: error description,<br/>return code, stderr lines]
        end

        subgraph "Generated Models"
            MODELS_DIR[models/]
            SPTHY_FILES[task_lemma_version.spthy<br/>Contains: generated Tamarin<br/>models from successful runs]
        end
    end

    OUTPUT_DIR --> SUCCESS_DIR
    OUTPUT_DIR --> FAILED_DIR
    OUTPUT_DIR --> MODELS_DIR

    SUCCESS_DIR --> SUCCESS_JSON
    FAILED_DIR --> FAILED_JSON
    MODELS_DIR --> SPTHY_FILES
```

### Output Structure Details

- **success/**: JSON files containing detailed results for successful task executions
- **failed/**: JSON files with error information and diagnostics for failed tasks
- **models/**: Generated .spthy model files from successful Tamarin runs

## Command Generation Process

ExecutableTask objects are converted to Tamarin command-line invocations:

```mermaid
flowchart TD
    EXECUTABLE_TASK[ExecutableTask Object] --> BUILD_CMD[Build Command Array]

    BUILD_CMD --> ADD_BINARY[Add Tamarin Binary Path]
    ADD_BINARY --> ADD_RTS[Add Haskell RTS Flags<br/>+RTS -Ncores -RTS]
    ADD_RTS --> ADD_THEORY[Add Theory File Path]
    ADD_THEORY --> ADD_PROVE{Specific Lemma?}

    ADD_PROVE -->|Yes| ADD_LEMMA[Add --prove=lemma_name]
    ADD_PROVE -->|No| ADD_ALL[Add --prove for all lemmas]

    ADD_LEMMA --> ADD_OPTIONS[Add Tamarin Options<br/>-v, --diff, etc.]
    ADD_ALL --> ADD_OPTIONS

    ADD_OPTIONS --> ADD_PREPROCESS[Add Preprocessor Flags<br/>-D=flag1 -D=flag2]
    ADD_PREPROCESS --> ADD_OUTPUT[Add Output File<br/>--output=result.txt]
    ADD_OUTPUT --> FINAL_COMMAND[Final Command Array]

    subgraph "Example Output"
        EXAMPLE["['tamarin-prover', '+RTS', '-N4', '-RTS',<br/>'protocol.spthy', '--prove=secrecy',<br/>'-v', '-D=GoodKeys', '--output=result.txt']"]
    end

    FINAL_COMMAND --> EXAMPLE
```

### Command Generation Features

- **Haskell RTS Integration**: Automatic inclusion of runtime system flags for performance control
- **Flexible Lemma Targeting**: Support for both individual lemma and complete protocol analysis
- **Option Inheritance**: Lemma-specific options can override task-level settings
- **Preprocessor Support**: Automatic formatting of preprocessor flags

## Error Handling Strategy

The system implements comprehensive error handling across all components:

```mermaid
graph TD
    subgraph "Error Types"
        CONFIG_ERROR[Configuration Errors<br/>JSON syntax, validation failures]
        VALIDATION_ERROR[Validation Errors<br/>Pydantic model violations]
        RESOURCE_ERROR[Resource Errors<br/>Insufficient system resources]
        EXECUTION_ERROR[Execution Errors<br/>Tamarin process failures]
        TIMEOUT_ERROR[Timeout Errors<br/>Task time limit exceeded]
        MEMORY_ERROR[Memory Limit Errors<br/>Process memory exceeded]
    end

    subgraph "Error Handling"
        EARLY_FAIL[Early Failure<br/>Stop execution immediately]
        GRACEFUL_DEGRADE[Graceful Degradation<br/>Continue other tasks]
        CLEANUP[Resource Cleanup<br/>Release allocated resources]
        USER_FEEDBACK[User Notification<br/>Rich error messages]
    end

    subgraph "Recovery Actions"
        FALLBACK[Apply System Fallbacks<br/>Use maximum available resources]
        RETRY[Retry Logic<br/>Limited retry attempts]
        PARTIAL_SUCCESS[Partial Success Reporting<br/>Report completed tasks]
    end

    CONFIG_ERROR --> EARLY_FAIL
    VALIDATION_ERROR --> EARLY_FAIL
    RESOURCE_ERROR --> FALLBACK
    EXECUTION_ERROR --> GRACEFUL_DEGRADE
    TIMEOUT_ERROR --> GRACEFUL_DEGRADE
    MEMORY_ERROR --> GRACEFUL_DEGRADE

    EARLY_FAIL --> USER_FEEDBACK
    GRACEFUL_DEGRADE --> CLEANUP
    FALLBACK --> RETRY
    CLEANUP --> PARTIAL_SUCCESS
    RETRY --> USER_FEEDBACK
    PARTIAL_SUCCESS --> USER_FEEDBACK
```

### Error Handling Principles

1. **Early Failure**: Configuration and validation errors stop execution immediately
2. **Graceful Degradation**: Task-level errors don't affect other tasks
3. **Resource Cleanup**: Automatic cleanup of allocated resources on failure
4. **User Communication**: Rich error messages with context and suggestions
5. **Partial Success**: Report successful tasks even when some fail

## Utility Components

### System Resources (`utils/system_resources.py`)

Provides system resource detection and validation capabilities:

- **Resource Detection**: Automatically detect available CPU cores and memory
- **Limit Resolution**: Convert "max" values to actual system limits
- **Validation**: Ensure requested resources don't exceed system capacity

### Notifications (`utils/notifications.py`)

Centralized user communication and logging system:

- **Rich Output**: Formatted console output with colors and progress bars
- **Debug Support**: Detailed debug information when enabled
- **Progress Tracking**: Real-time progress updates during execution
- **Error Reporting**: Structured error messages with context

## Design Patterns and Principles

### 1. Async/Await Pattern
- Enables non-blocking I/O operations for better performance
- Supports concurrent task execution without thread complexity
- Allows real-time progress monitoring and user interaction

### 2. Manager Pattern
- Separate managers for different concerns (Config, Process, Task, Resource, Output)
- Clear separation of responsibilities and single responsibility principle
- Facilitates testing, maintenance, and extensibility

### 3. Data Transformation Pipeline
- Structured transformation: JSON → Pydantic Models → ExecutableTask Objects → Commands
- Type safety throughout the pipeline with Pydantic validation
- Clear data flow with validation at each stage

### 4. Resource Pool Management
- Global resource tracking with intelligent scheduling
- Automatic resource allocation and deallocation
- Graceful handling of resource constraints

This architecture provides a robust, scalable foundation for Tamarin protocol verification automation while maintaining clear separation of concerns, comprehensive error handling, and efficient resource utilization.
