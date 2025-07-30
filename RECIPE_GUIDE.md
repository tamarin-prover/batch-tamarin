# Batch Tamarin Configuration Documentation

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
- **`global_max_cores`** (integer or "max", **required**): Maximum CPU cores available
- **`global_max_memory`** (integer or "max", **required**): Maximum memory in GB available
- **`default_timeout`** (integer, **required**): Default timeout in seconds
- **`output_directory`** (string, **required**): Base directory for all output files

### Tamarin Versions (`tamarin_versions`)

Defines named aliases for different Tamarin prover executables:

```json
{
  "tamarin_versions": {
    "stable": {
      "path": "tamarin-binaries/tamarin-prover-1.8/1.8.0/bin/tamarin-prover"
    },
    "dev": {
      "path": "tamarin-binaries/tamarin-prover-dev/1.11.0/bin/tamarin-prover",
      "version": "1.11.0",
      "test_success": true
    }
  }
}
```

#### Properties per alias:
- **`path`** (string, **required**): File path to the Tamarin prover executable
- **`version`** (string, optional): Version identifier for this Tamarin prover
- **`test_success`** (boolean, optional): Whether this executable passed integrity tests

`version` and `test_success` are overwritten by the `--revalidate` flag. These fields are usually filled by the UI tool to generate a JSON recipe, there is no real reason to use them manually.

### Tasks (`tasks`)

Tasks define individual Tamarin analysis configurations. Each task is identified by a unique key:

```json
{
  "tasks": {
    "example_protocol_basic": {
      "theory_file": "protocols/example.spthy",
      "tamarin_versions": ["stable", "dev"],
      "output_file_prefix": "example_basic",
      "resources": {
        "max_cores": 4,
        "max_memory": 8,
        "timeout": 3200
      }
    }
  }
}
```

#### Properties:
- **`theory_file`** (string, **required**): Path to the `.spthy` theory file to analyze
- **`tamarin_versions`** (array of strings, **required**): List of Tamarin version aliases to run this task on
- **`output_file_prefix`** (string, **required**): Prefix for output file names, format : `task_id = {output_file_prefix}\_{task_suffix}.spthy`

The `task_suffix` is formatted like following : {lemma}\_{tamarin_version} (with lemma added only if a lemma is specified in config)

- **`lemmas`** (array, optional): Lemmas to prove. If empty or omitted, all lemmas are proved using `--prove`. Supports prefix matching for convenient lemma selection
- **`tamarin_options`** (array of strings, optional): Additional command-line options for Tamarin
- **`preprocess_flags`** (array of strings, optional): Preprocessor flags (passed as `-D=flag`)
- **`resources`** (object, optional): Resource allocation for this task

## Lemma Configuration

Lemmas support comprehensive per-lemma configuration with full inheritance from task-level settings:

```json
{
  "lemmas": [
    {
      "name": "secrecy",
      "tamarin_versions": ["stable"],
      "resources": {
        "max_cores": 2,
        "max_memory": 4,
        "timeout": 1200
      }
    },
    {
      "name": "authentication",
      "tamarin_options": ["--heuristic=S"],
      "preprocess_flags": ["AuthOptimization"],
      "resources": {
        "max_cores": 8,
        "max_memory": 16,
        "timeout": 3600
      }
    },
    {
      "name": "basic_lemma"
      // Inherits all task-level configuration
    }
  ]
}
```

#### Lemma Properties:
- **`name`** (string, **required**): Name of the lemma to prove
- **`tamarin_versions`** (array of strings, optional): Override which tamarin versions to use for this lemma
- **`tamarin_options`** (array of strings, optional): Override tamarin command-line options for this lemma
- **`preprocess_flags`** (array of strings, optional): Override preprocessor flags for this lemma
- **`resources`** (object, optional): Override resource allocation for this lemma

**Override Behavior**: Lemma-level properties completely replace task-level properties (no merging).

### Lemma Selection and Prefix Matching

When using the interactive `init` command, you can efficiently select lemmas using prefix matching:

```bash
batch-tamarin init protocol.spthy
```

During the interactive configuration process, you can:
- **Prefix Matching**: Type a prefix (e.g., `auth`) to show all lemmas starting with that prefix
- **Multiple Selection**: Select multiple lemmas by their prefixes
- **All Lemmas**: Leave empty to include all lemmas found in the theory file

Example: If your `.spthy` file contains lemmas like `authentication_lemma`, `auth_secrecy`, and `authorization_check`, typing `auth` will show all three for easy selection.

## Resource Management
```json
{
  "resources": {
    "max_cores": 4,
    "max_memory": 8,
    "timeout": 3200
  }
}
```

### Default Resources
When a task doesn't specify `resources`, the following defaults are used:
- **Cores**: `global_max_cores` from previously defined `global_config`
- **Memory**: `global_max_memory`, same method
- **Timeout**: `default_timeout`, same method

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

## Output File Naming

Output files are automatically named based on the configuration to avoid conflicts:

### Tasks without specific lemmas:
- Pattern: `{output_file}_{tamarin_version}`
- Example: `results.txt` → `results_stable.txt`, `results_dev.txt`

### Tasks with specific lemmas:
- Pattern: `{output_file}_{lemma_name}_{tamarin_version}`
- Example: With lemma "auth" → `results_auth_stable.txt`, `results_auth_dev.txt`

## Result Caching

Batch Tamarin automatically caches execution results to avoid re-running identical tasks. The cache is based on:
- Theory file content (checksum)
- Task configuration (lemma, options, flags)
- Tamarin executable version

**Cache Management:**
```bash
# Clear all cached results
batch-tamarin --rm-cache

# View cache statistics (shows hit/miss ratios)
# Cache info is displayed during normal execution
```

Tasks are automatically skipped if their cached results are still valid, significantly reducing execution time for repeated runs.

## Example Configurations

See the following examples for complete working configurations:
- [`example_config.json`](example_config.json) - Basic usage with enhanced lemma configuration
- [`wpa2.json`](wpa2.json) - Advanced per-lemma resource allocation and version selection
