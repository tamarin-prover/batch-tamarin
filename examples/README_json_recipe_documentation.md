# Tamarin Wrapper Configuration Documentation

## Overview

The configuration uses a JSON structure with three main sections:
- **config**: Global system configuration
- **tamarin_versions**: Named aliases for different Tamarin executables
- **tasks**: Individual analysis tasks with specific parameters

## Configuration Structure

### Global Configuration (`config`)

The global configuration section defines system-wide settings:

```json
{
  "config": {
    "global_max_cores": 8,
    "global_max_memory": 16,
    "default_timeout": 7200,
    "output_directory": "./results"
  }
}
```

#### Properties:
- **`global_max_cores`** (integer, required): Maximum CPU cores available across all tasks
- **`global_max_memory`** (integer, required): Maximum memory in GB available across all tasks
- **`default_timeout`** (integer, required): Default timeout in seconds when tasks don't specify resources
- **`output_directory`** (string, required): Base directory for all output files

### Tamarin Versions (`tamarin_versions`)

Defines named aliases for different Tamarin prover executables:

```json
{
  "tamarin_versions": {
    "stable": {
      "path": "tamarin-binaries/tamarin-prover-1.8/1.8.0/bin/tamarin-prover",
      "version": "1.8.0",
      "test_success": true
    },
    "dev": {
      "path": "tamarin-binaries/tamarin-prover-dev/.stack-work/dist/aarch64-osx/ghc-9.6.6/build/tamarin-prover/tamarin-prover",
      "version": "1.11.0",
      "test_success": true
    }
  }
}
```

#### Properties per alias:
- **`path`** (string, required): File path to the Tamarin prover executable
- **`version`** (string, optional): Version identifier for this Tamarin prover
- **`test_success`** (boolean, optional): Whether this executable passed connectivity tests
`version` and `test_success` will be created by the UI in case of autodetection of tamarin or if `--revalidate` flag is given

### Tasks (`tasks`)

Tasks define individual Tamarin analysis configurations. Each task is identified by a unique key:

```json
{
  "tasks": {
    "example_protocol_basic": {
      "theory_file": "protocols/example.spthy",
      "tamarin_versions": ["stable", "dev"],
      "output_file": "example_basic_results.txt",
      "ressources": {
        "max_cores": 4,
        "max_memory": 8,
        "task_timeout": 3200
      }
    }
  }
}
```

#### Required Properties:
- **`theory_file`** (string): Path to the `.spthy` theory file to analyze
- **`tamarin_versions`** (array of strings): List of Tamarin version aliases to run this task on
- **`output_file`** (string): Output file name for results (relative to `output_directory`)

#### Optional Properties:
- **`lemmas`** (array): Lemmas to prove. If empty or omitted, all lemmas are proved using `--prove`
- **`tamarin_options`** (array of strings): Additional command-line options for Tamarin
- **`preprocess_flags`** (array of strings): Preprocessor flags (passed as `-D=flag`)
- **`ressources`** (object): Resource allocation for this task

## Lemma Configuration

Lemmas can be specified as objects with individual timeouts:

```json
{
  "lemmas": [
    {
      "name": "secrecy",
      "timeout": 1200
    },
    {
      "name": "authentication",
      "timeout": 900
    },
    {
      "name": "basic_lemma"
    }
  ]
}
```

#### Lemma Properties:
- **`name`** (string, required): Name of the lemma to prove
- **`timeout`** (integer, optional): Specific timeout in seconds for this lemma

## Resource Management

### Default Resources
When a task doesn't specify `ressources`, the following defaults are used:
- **Cores**: 4
- **Memory**: 8 GB
- **Timeout**: 3600 seconds

### Task-Specific Resources
Tasks can override defaults in the `ressources` section:

```json
{
  "ressources": {
    "max_cores": 4,
    "max_memory": 8,
    "task_timeout": 3200
  }
}
```

### Smart Resource Allocation
The system will intelligently allocate resources based on the global limits defined in the config and the limits of each task.


## Command Generation

For each task, the system generates Tamarin commands following this pattern:

```bash
tamarin-prover [theory_file] [--prove=lemma] [tamarin_options] [preprocess_flags] --output=[output_file]
```

### Examples:

**Basic execution** (prove all lemmas):
```bash
tamarin-prover protocols/example.spthy --prove --output=example_basic_results.txt
```

**Specific lemmas with options**:
```bash
tamarin-prover protocols/complex_protocol.spthy --prove=secrecy --prove=authentication --diff -D=GoodKeysOnly -D=bindkttoct --output=complex_results.txt
```

## Multi-Version Execution

When a task specifies multiple `tamarin_versions`, the same parameters are duplicated across each version:

```json
{
  "tamarin_versions": ["stable", "dev"]
}
```

This creates separate executions:
1. Using the "stable" Tamarin version with all task parameters
2. Using the "dev" Tamarin version with identical parameters

## Example Configuration

See [`example_config_unimplemented.json`](example_config_unimplemented.json) for a complete working example demonstrating all features.
