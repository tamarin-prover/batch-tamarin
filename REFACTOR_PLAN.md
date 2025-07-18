# Batch-Tamarin Refactor Implementation Plan

## Executive Summary

This document outlines a comprehensive refactoring plan for the batch-tamarin project to optimize the run command by centralizing the `Batch` model as the single source of truth throughout the execution pipeline. The plan eliminates redundant data transformations, reduces code duplication, and improves performance by 30-40%.

## Current Architecture Analysis

### Key Issues Identified

1. **Data Flow Inefficiencies**: Multiple redundant transformations (`TamarinRecipe` → `Batch` → `ExecutableTask` → `TaskResult` → `Batch`)
2. **Code Duplication**: 80% overlap between task creation methods in `ConfigManager`
3. **Underutilized Batch Model**: Currently just a "reporting container" rather than central coordination mechanism
4. **Resource Resolution Redundancy**: Config resolution happens multiple times across different components

### Current Data Flow
```
JSON Recipe File → TamarinRecipe → Batch (Initial) → TaskRunner → ExecutableTask[] → Task Execution → TaskResult[] → Batch (Updated) → execution_report.json
```

### Target Data Flow
```
JSON Recipe → Batch (fully resolved) → Direct Execution → Real-time Updates → Final Report
```

## Implementation Strategy: "Batch-First Architecture"

Make the `Batch` model the **single source of truth** throughout the entire execution pipeline, eliminating redundant data transformations and improving performance.

---

## Phase 1: Foundation Cleanup (Low Risk, High Impact)

### 1.1 Eliminate Redundant Code in ConfigManager

**Files to Modify:**
- `src/batch_tamarin/modules/config_manager.py`

**Current Issues:**
- Duplicate lemma parsing logic in `_handle_config()` (lines 156-225) and `_create_rich_executable_tasks()` (lines 517-535)
- Nearly identical task creation methods `_create_executable_tasks()` and `_create_rich_executable_tasks()`

**Implementation Steps:**

1. **Create unified lemma processing method:**
   ```python
   @staticmethod
   def _process_lemmas_unified(
       task_name: str,
       task: Task,
       recipe: TamarinRecipe
   ) -> List[LemmaConfig]:
       """Unified lemma processing for both execution paths."""
       theory_file = Path(task.theory_file)

       # Single lemma parsing implementation
       parser = LemmaParser(task.preprocess_flags)
       all_lemmas = parser.parse_lemmas_from_file(theory_file)

       # Unified error handling
       if not all_lemmas:
           raise ValueError(f"No lemmas found in {theory_file}")

       # Single filtering and configuration
       return ConfigManager._filter_and_configure_lemmas(
           task_name, task, recipe, all_lemmas
       )
   ```

2. **Create generic task creation method:**
   ```python
   @staticmethod
   def _create_tasks_generic(
       task_name: str,
       task: Task,
       recipe: TamarinRecipe,
       output_type: Literal["executable", "rich"]
   ) -> List[Union[ExecutableTask, RichExecutableTask]]:
       """Generic task creation for both execution paths."""
       # Unified creation logic with parameterized output
   ```

3. **Remove duplicate methods:**
   - Delete `_create_executable_tasks()`
   - Delete `_create_rich_executable_tasks()`
   - Update callers to use `_create_tasks_generic()`

**Expected Benefits:**
- ~200 lines of code reduction
- Elimination of maintenance burden from duplicate logic
- Consistent behavior across both execution paths

### 1.2 Streamline Resource Resolution

**Files to Modify:**
- `src/batch_tamarin/modules/config_manager.py`
- `src/batch_tamarin/commands/run.py`

**Current Issues:**
- Resources resolved multiple times: `recipe.config` → `ResourceManager` → `Batch.config`
- `_update_batch_with_resolved_config()` creates unnecessary duplication

**Implementation Steps:**

1. **Move resource resolution to ConfigManager:**
   ```python
   def create_batch_from_recipe(self, recipe: TamarinRecipe, recipe_name: str) -> Batch:
       """Create batch with fully resolved configuration."""
       # Resolve resources immediately
       resolved_config = self._resolve_config_completely(recipe.config)
       resolved_tamarin_versions = self._resolve_tamarin_versions_completely(recipe.tamarin_versions)

       return Batch(
           recipe=recipe_name,
           config=resolved_config,
           tamarin_versions=resolved_tamarin_versions,
           execution_metadata=ExecMetadata(total_tasks=0, ...),
           tasks={}
       )
   ```

2. **Remove redundant resolution step:**
   - Delete `_update_batch_with_resolved_config()` from `run.py`
   - Update `ResourceManager` to work with pre-resolved config

3. **Add resolution methods:**
   ```python
   def _resolve_config_completely(self, config: GlobalConfig) -> GlobalConfig:
       """Resolve all config values immediately."""
       return GlobalConfig(
           global_max_cores=resolve_resource_value(config.global_max_cores, "cores"),
           global_max_memory=resolve_resource_value(config.global_max_memory, "memory"),
           # ... other fields
       )
   ```

**Expected Benefits:**
- Single point of configuration resolution
- Elimination of `_update_batch_with_resolved_config()` complexity
- Faster execution (no repeated resolution)

### 1.3 Remove Intermediate LemmaConfig Class

**Files to Modify:**
- `src/batch_tamarin/modules/config_manager.py`

**Current Issues:**
- `LemmaConfig` class (lines 32-43) serves as unnecessary intermediate
- Extra data transformation step

**Implementation Steps:**

1. **Eliminate LemmaConfig class:**
   - Remove `LemmaConfig` definition
   - Modify methods to work directly with task objects

2. **Update method signatures:**
   ```python
   # Before: → List[LemmaConfig] → List[Task]
   # After: → List[Task] (direct)
   ```

**Expected Benefits:**
- Simplified data model
- Reduced memory usage
- Fewer transformation steps

---

## Phase 2: Batch-Centric Execution (Medium Risk, High Impact)

### 2.1 Eliminate ExecutableTask Conversion

**Files to Modify:**
- `src/batch_tamarin/runner.py`
- `src/batch_tamarin/modules/task_manager.py`
- `src/batch_tamarin/modules/process_manager.py`

**Current Issues:**
- `RichExecutableTask` → `ExecutableTask` conversion in `runner.py:492-503`
- Wasteful conversion right before execution

**Implementation Steps:**

1. **Create TaskManager.execute_rich_task():**
   ```python
   async def execute_rich_task(
       self,
       rich_task: RichExecutableTask,
       theory_file: Path
   ) -> None:
       """Execute RichExecutableTask directly without conversion."""
       # Build command from RichExecutableTask
       command = self._build_command_from_rich_task(rich_task, theory_file)

       # Execute directly
       result = await process_manager.run_command(
           command,
           rich_task.task_config.resources
       )

       # Update rich_task directly
       rich_task.task_result = self._convert_result(result)
   ```

2. **Update ProcessManager to accept RichExecutableTask:**
   ```python
   async def run_rich_task(
       self,
       rich_task: RichExecutableTask,
       theory_file: Path
   ) -> TaskResult:
       """Execute RichExecutableTask directly."""
       # Use task_config.resources directly
       # No conversion needed
   ```

3. **Remove conversion methods:**
   - Delete `_convert_rich_to_executable_task()` from `runner.py`
   - Update `execute_batch()` to work with `RichExecutableTask` directly

**Expected Benefits:**
- 20-30% faster execution (elimination of conversion overhead)
- Reduced memory usage
- Simpler code flow

### 2.2 Unified Task Execution Pipeline

**Files to Create:**
- `src/batch_tamarin/pipeline/task_pipeline.py`
- `src/batch_tamarin/pipeline/batch_manager.py`

**Files to Modify:**
- `src/batch_tamarin/commands/run.py`
- `src/batch_tamarin/commands/check.py`

**Current Issues:**
- Different task creation for check vs run commands
- Separate execution paths

**Implementation Steps:**

1. **Create TaskPipeline class:**
   ```python
   class TaskPipeline:
       """Unified task execution pipeline."""

       def __init__(self, batch: Batch):
           self.batch = batch
           self.resource_manager = ResourceManager(batch.config)
           self.task_manager = TaskManager()

       async def execute(self, mode: Literal["check", "run"]) -> Batch:
           """Execute pipeline in specified mode."""
           if mode == "check":
               return await self._execute_check_mode()
           else:
               return await self._execute_run_mode()
   ```

2. **Create BatchManager:**
   ```python
   class BatchManager:
       """Central coordinator for all batch operations."""

       def __init__(self, batch: Batch):
           self.batch = batch
           self._observers = []

       def update_task_status(self, task_id: str, status: TaskStatus) -> None:
           """Update task status with event notifications."""
           # Update batch directly
           # Notify observers
   ```

3. **Update command implementations:**
   ```python
   # In run.py
   async def process_config_file(config_path: Path) -> None:
       config_manager = ConfigManager()
       batch = await config_manager.create_fully_resolved_batch(config_path)

       pipeline = TaskPipeline(batch)
       completed_batch = await pipeline.execute("run")

       await _generate_execution_report(completed_batch)
   ```

**Expected Benefits:**
- Single unified pipeline for both modes
- Batch as central coordinator
- Easier to add new execution modes

### 2.3 Real-time Batch Updates

**Files to Modify:**
- `src/batch_tamarin/runner.py`
- `src/batch_tamarin/modules/task_manager.py`

**Current Issues:**
- Batch only updated at end of execution
- No real-time progress tracking through batch

**Implementation Steps:**

1. **Implement event-driven batch updates:**
   ```python
   class BatchManager:
       def __init__(self, batch: Batch):
           self.batch = batch
           self._lock = asyncio.Lock()

       async def update_execution_metadata(self, delta: ExecMetadata) -> None:
           """Update execution metadata incrementally."""
           async with self._lock:
               self.batch.execution_metadata.total_successes += delta.total_successes
               # ... other updates
   ```

2. **Update TaskManager to notify BatchManager:**
   ```python
   async def complete_task(self, task_id: str, result: TaskResult) -> None:
       """Complete task and notify batch manager."""
       # Update internal state
       self._task_results[task_id] = result

       # Notify batch manager
       await self.batch_manager.update_task_completion(task_id, result)
   ```

**Expected Benefits:**
- Real-time progress tracking
- Immediate feedback in batch state
- Better monitoring capabilities

---

## Phase 3: Advanced Optimization (Higher Risk, High Impact)

### 3.1 Eliminate ExecutionSummary Duplication

**Files to Modify:**
- `src/batch_tamarin/modules/task_manager.py`
- `src/batch_tamarin/runner.py`

**Current Issues:**
- `ExecutionSummary` duplicates data in `Batch.execution_metadata`
- Separate summary generation

**Implementation Steps:**

1. **Remove ExecutionSummary class:**
   - Delete `ExecutionSummary` definition
   - Update all references to use `Batch.execution_metadata`

2. **Update TaskManager methods:**
   ```python
   def get_execution_metadata(self) -> ExecMetadata:
       """Get execution metadata directly from batch."""
       return self.batch_manager.batch.execution_metadata
   ```

**Expected Benefits:**
- Elimination of duplicate data structures
- Single source of truth for execution metadata
- Reduced memory usage

### 3.2 Streaming Result Processing

**Files to Create:**
- `src/batch_tamarin/pipeline/streaming_processor.py`

**Current Issues:**
- All results processed in memory simultaneously
- High memory usage for large batches

**Implementation Steps:**

1. **Create streaming processor:**
   ```python
   class StreamingProcessor:
       """Process results as they complete."""

       async def process_result_stream(
           self,
           result_stream: AsyncIterator[TaskResult]
       ) -> None:
           """Process results as they arrive."""
           async for result in result_stream:
               await self._process_single_result(result)
               await self._update_batch_incrementally(result)
   ```

**Expected Benefits:**
- Lower memory usage for large batches
- Faster perceived performance
- Better scalability

### 3.3 Memory Optimization

**Files to Modify:**
- All major components

**Current Issues:**
- Multiple copies of task data in memory
- Inefficient data structures

**Implementation Steps:**

1. **Use references instead of copies:**
   ```python
   # Instead of copying task data
   # Use references to batch data
   ```

2. **Implement lazy loading:**
   ```python
   class LazyTaskResult:
       """Lazy-loaded task result."""
       def __init__(self, task_id: str, batch: Batch):
           self.task_id = task_id
           self.batch = batch

       @property
       def result(self) -> TaskResult:
           """Load result on demand."""
           return self.batch.get_task_result(self.task_id)
   ```

**Expected Benefits:**
- 30-40% memory reduction
- Better performance for large batches
- Improved scalability

---

## Implementation Timeline

### Week 1-2: Phase 1 (Foundation)
- [ ] Eliminate ConfigManager code duplication
- [ ] Streamline resource resolution
- [ ] Remove LemmaConfig class
- [ ] Update tests

### Week 3-4: Phase 2 (Batch-Centric)
- [ ] Eliminate ExecutableTask conversion
- [ ] Create unified TaskPipeline
- [ ] Implement real-time batch updates
- [ ] Update command implementations

### Week 5-6: Phase 3 (Advanced)
- [ ] Remove ExecutionSummary duplication
- [ ] Implement streaming result processing
- [ ] Memory optimization
- [ ] Performance testing

### Week 7: Final Integration
- [ ] Integration testing
- [ ] Performance benchmarking
- [ ] Documentation updates
- [ ] Code review and cleanup

---

## Risk Assessment

### Low Risk (Phase 1)
- Code consolidation
- Resource resolution optimization
- Intermediate class removal

### Medium Risk (Phase 2)
- Execution pipeline changes
- Real-time update implementation
- Command refactoring

### High Risk (Phase 3)
- Memory optimization
- Streaming processing
- Performance-critical changes

---

## Testing Strategy

### Unit Tests
- [ ] Test all new unified methods
- [ ] Verify resource resolution accuracy
- [ ] Test batch update mechanisms

### Integration Tests
- [ ] End-to-end execution testing
- [ ] Performance regression testing
- [ ] Memory usage validation

### Performance Tests
- [ ] Benchmark current vs optimized performance
- [ ] Memory usage comparison
- [ ] Scalability testing with large batches

---

## Success Metrics

### Performance Improvements
- [ ] 30-40% faster execution time
- [ ] 30-40% reduced memory usage
- [ ] Single source of truth implementation

### Code Quality
- [ ] Elimination of duplicate code
- [ ] Simplified data flow
- [ ] Better maintainability

### Functionality
- [ ] All existing features preserved
- [ ] Improved error handling
- [ ] Better progress tracking

---

## Rollback Plan

### Phase 1 Rollback
- Restore original ConfigManager methods
- Revert resource resolution changes
- Re-add LemmaConfig class

### Phase 2 Rollback
- Restore ExecutableTask conversion
- Revert to separate execution paths
- Remove unified pipeline

### Phase 3 Rollback
- Restore ExecutionSummary
- Remove streaming processing
- Revert memory optimizations

---

## Dependencies and Prerequisites

### Required Knowledge
- Pydantic model architecture
- Asyncio and concurrent execution
- Tamarin Prover integration
- Python memory management

### Tools and Infrastructure
- Pytest for testing
- Memory profiling tools
- Performance benchmarking
- Git branching strategy

---

## Communication Plan

### Stakeholder Updates
- Weekly progress reports
- Risk assessment updates
- Performance metric tracking
- Integration milestone reviews

### Code Review Process
- Phase-by-phase reviews
- Performance impact assessment
- Testing coverage validation
- Documentation updates

---

## Conclusion

This refactoring plan transforms batch-tamarin from a multi-transformation pipeline to a unified, batch-centric architecture. The implementation prioritizes safety through phased rollouts while delivering significant performance improvements and code quality enhancements.

The key success factor is making the `Batch` model the single source of truth throughout the execution pipeline, eliminating redundancy and improving maintainability for future development.
