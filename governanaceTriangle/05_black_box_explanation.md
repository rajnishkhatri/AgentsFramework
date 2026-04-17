# Black Box Recorder: Step-by-Step Explanation

## Table of Contents

1. [Introduction](#introduction)
2. [Data Models](#data-models)
3. [BlackBoxRecorder Class](#blackboxrecorder-class)
4. [Complete Data Flow Example](#complete-data-flow-example)
5. [Real-World Example: Invoice Processing Cascade Failure](#real-world-example-invoice-processing-cascade-failure)

---

## Introduction

### Purpose

The `BlackBoxRecorder` is an aviation-style flight recorder for agent workflows. Just as aircraft black boxes record critical flight data for post-incident analysis, this module captures comprehensive records of all agent activities for:

- **Post-incident analysis and debugging**: When something goes wrong, you can replay exactly what happened
- **Compliance auditing**: Maintain complete records of parameter changes and decision-making processes
- **Workflow replay and analysis**: Understand how workflows executed in production
- **Cascade failure investigation**: Trace how one failure led to another

### Key Capabilities

The black box recorder captures four main types of data:

1. **Task Plans**: Steps, dependencies, and rollback points
2. **Collaborators**: Which agents participated in the workflow
3. **Parameter Substitutions**: Before/after values with reasoning for parameter changes
4. **Execution Traces**: Complete execution history with decision points and outcomes

### Relationship to Lesson-16 Patterns

The `BlackBoxRecorder` extends patterns from lesson-16:

- **`lesson-16/backend/reliability/audit_log.py`**: Extends AuditLogger patterns for structured logging
- **`lesson-16/backend/reliability/checkpoint.py`**: Reuses persistence patterns for disk storage

### Storage Structure

Recordings are stored in a structured directory hierarchy:

```
cache/
└── black_box_recordings/
    └── {workflow_id}/
        ├── {task_id}_plan.json
        ├── {task_id}_collaborators.json
        ├── {task_id}_params.json
        └── {task_id}_trace.json
```

---

## Data Models

The black box recorder uses Pydantic models to ensure type safety and data validation. Let's examine each model with real examples from the invoice processing workflow.

### EventType Enum

The `EventType` enum defines all possible event types that can occur during workflow execution:

```python
class EventType(str, Enum):
    STEP_START = "step_start"
    STEP_END = "step_end"
    DECISION = "decision"
    ERROR = "error"
    CHECKPOINT = "checkpoint"
    PARAMETER_CHANGE = "parameter_change"
    COLLABORATOR_JOIN = "collaborator_join"
    COLLABORATOR_LEAVE = "collaborator_leave"
    ROLLBACK = "rollback"
```

These event types are used in `TraceEvent` objects to categorize what happened at each point in the execution.

### PlanStep

A `PlanStep` represents an individual step in a task plan. It defines what needs to be done, by whom, and what inputs/outputs are expected.

**Code Definition:**

```python
class PlanStep(BaseModel):
    step_id: str
    description: str
    agent_id: str
    expected_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    is_critical: bool = True
    order: int = 0
```

**Real Example from `task-extract-invoice_plan.json`:**

```json
{
  "step_id": "step-1-extract",
  "description": "Extract vendor and amount from invoice",
  "agent_id": "invoice-extractor",
  "expected_inputs": ["invoice_text"],
  "expected_outputs": ["vendor_name", "amount"],
  "timeout_seconds": 60,
  "is_critical": true,
  "order": 1
}
```

**Explanation:**
- `step_id`: Unique identifier for this step
- `description`: Human-readable description of what the step does
- `agent_id`: Which agent is responsible for executing this step
- `expected_inputs`: What data this step needs to receive
- `expected_outputs`: What data this step will produce
- `timeout_seconds`: Maximum time allowed for this step (60 seconds)
- `is_critical`: If `true`, failure of this step stops the entire workflow
- `order`: Execution order (1 = first step)

### TaskPlan

A `TaskPlan` contains the complete plan for a task, including all steps, their dependencies, and rollback points.

**Code Definition:**

```python
class TaskPlan(BaseModel):
    plan_id: str
    task_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    steps: list[PlanStep] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    rollback_points: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Real Example from `task-extract-invoice_plan.json`:**

```json
{
  "plan_id": "plan-inv-001",
  "task_id": "task-extract-invoice",
  "created_at": "2025-11-28T19:15:15.583451Z",
  "steps": [
    {
      "step_id": "step-1-extract",
      "description": "Extract vendor and amount from invoice",
      "agent_id": "invoice-extractor",
      "expected_inputs": ["invoice_text"],
      "expected_outputs": ["vendor_name", "amount"],
      "timeout_seconds": 60,
      "is_critical": true,
      "order": 1
    },
    {
      "step_id": "step-2-validate",
      "description": "Validate extracted data against database",
      "agent_id": "data-validator",
      "expected_inputs": ["vendor_name", "amount"],
      "expected_outputs": ["validation_result", "vendor_id"],
      "timeout_seconds": 30,
      "is_critical": true,
      "order": 2
    }
  ],
  "dependencies": {
    "step-2-validate": ["step-1-extract"]
  },
  "rollback_points": ["step-1-extract"],
  "metadata": {}
}
```

**Explanation:**
- `plan_id`: Unique identifier for this plan
- `task_id`: Which task this plan is for
- `created_at`: When the plan was created
- `steps`: List of all steps to execute
- `dependencies`: Maps step IDs to their prerequisite steps. Here, `step-2-validate` depends on `step-1-extract`, meaning validation can't start until extraction completes
- `rollback_points`: Steps that can be safely rolled back to if something goes wrong. Here, we can rollback to `step-1-extract`
- `metadata`: Additional contextual information

### AgentInfo

`AgentInfo` tracks which agents participated in a workflow and their roles.

**Code Definition:**

```python
class AgentInfo(BaseModel):
    agent_id: str
    agent_name: str
    role: str
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    capabilities: list[str] = Field(default_factory=list)
```

**Real Example from `task-extract-invoice_collaborators.json`:**

```json
[
  {
    "agent_id": "invoice-extractor-v2",
    "agent_name": "Invoice Extractor",
    "role": "extraction",
    "joined_at": "2025-11-27T14:00:00Z",
    "capabilities": ["extraction", "ocr"]
  },
  {
    "agent_id": "invoice-validator-v1",
    "agent_name": "Amount Validator",
    "role": "validation",
    "joined_at": "2025-11-27T14:00:12Z",
    "capabilities": ["validation", "database_lookup"]
  }
]
```

**Explanation:**
- `agent_id`: Unique identifier for the agent
- `agent_name`: Human-readable name
- `role`: The agent's role in the workflow (e.g., "extraction", "validation")
- `joined_at`: Timestamp when the agent joined the workflow
- `capabilities`: What capabilities this agent provides (e.g., "extraction", "ocr", "validation", "database_lookup")

Notice that the validator joined 12 seconds after the extractor, which matches the execution timeline.

### TraceEvent

A `TraceEvent` represents a single event that occurred during workflow execution. This is the atomic unit of execution tracking.

**Code Definition:**

```python
class TraceEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: EventType
    agent_id: str | None = None
    step_id: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Real Examples from `task-extract-invoice_trace.json`:**

**Example 1: Step Start Event**
```json
{
  "event_id": "evt-001",
  "timestamp": "2025-11-27T14:00:00Z",
  "event_type": "step_start",
  "agent_id": "invoice-extractor-v2",
  "step_id": "extract_vendor",
  "input_hash": null,
  "output_hash": null,
  "duration_ms": null,
  "metadata": {}
}
```

**Example 2: Decision Event**
```json
{
  "event_id": "evt-003",
  "timestamp": "2025-11-27T14:00:05Z",
  "event_type": "decision",
  "agent_id": "invoice-extractor-v2",
  "step_id": "extract_vendor",
  "input_hash": null,
  "output_hash": null,
  "duration_ms": null,
  "metadata": {
    "decision": "Use GPT-4 for OCR correction",
    "alternatives": ["GPT-3.5", "Claude", "Rule-based"],
    "rationale": "Higher accuracy needed for noisy scans"
  }
}
```

**Example 3: Error Event**
```json
{
  "event_id": "evt-010",
  "timestamp": "2025-11-27T14:00:15Z",
  "event_type": "error",
  "agent_id": "invoice-validator-v1",
  "step_id": "validate_amount",
  "input_hash": null,
  "output_hash": null,
  "duration_ms": null,
  "metadata": {
    "error_message": "Confidence threshold too high (0.95) - no valid results",
    "error_type": "ValidationError",
    "is_recoverable": false,
    "stack_trace": "ValidationError: All results below threshold 0.95..."
  }
}
```

**Example 4: Step End Event**
```json
{
  "event_id": "evt-006",
  "timestamp": "2025-11-27T14:00:12Z",
  "event_type": "step_end",
  "agent_id": "invoice-extractor-v2",
  "step_id": "extract_vendor",
  "input_hash": null,
  "output_hash": null,
  "duration_ms": 12000,
  "metadata": {
    "success": true,
    "confidence": 0.92
  }
}
```

**Explanation:**
- `event_id`: Unique identifier for this event
- `timestamp`: When the event occurred
- `event_type`: Type of event (from `EventType` enum)
- `agent_id`: Which agent was involved
- `step_id`: Which step this event relates to
- `input_hash`/`output_hash`: SHA256 hashes for integrity verification (optional)
- `duration_ms`: How long the operation took (for step_end events)
- `metadata`: Additional context-specific data (decisions, errors, checkpoints, etc.)

### ExecutionTrace

An `ExecutionTrace` contains the complete execution history for a task, including all events in chronological order.

**Code Definition:**

```python
class ExecutionTrace(BaseModel):
    trace_id: str
    task_id: str
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    events: list[TraceEvent] = Field(default_factory=list)
    final_outcome: str | None = None
    error_chain: list[str] | None = None
```

**Real Example from `task-extract-invoice_trace.json` (abbreviated):**

```json
{
  "trace_id": "trace-invoice-processing-001",
  "task_id": "invoice-processing-001",
  "start_time": "2025-11-27T14:00:00Z",
  "end_time": "2025-11-27T14:00:18Z",
  "events": [
    // ... 13 events in chronological order ...
  ],
  "final_outcome": "failed",
  "error_chain": [
    "Cascade failure: validator crashed after parameter change",
    "Parameter substitution (confidence_threshold: 0.8 → 0.95) caused empty validation results"
  ]
}
```

**Explanation:**
- `trace_id`: Unique identifier for this trace
- `task_id`: Which task this trace is for
- `start_time`: When execution started
- `end_time`: When execution ended (null if still running)
- `events`: All events in chronological order
- `final_outcome`: Final status ("success", "failed", "timeout", "cancelled")
- `error_chain`: List of error messages showing how failures cascaded

The `error_chain` is particularly useful for understanding cascade failures - it shows how one error led to another.

### ParameterSubstitution

A `ParameterSubstitution` records when a parameter value changed during execution, including the reason for the change.

**Code Definition:**

```python
class ParameterSubstitution(BaseModel):
    param_name: str
    old_value: str
    new_value: str
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_id: str | None = None
```

**Real Example from `task-extract-invoice_params.json`:**

```json
{
  "param_name": "confidence_threshold",
  "old_value": "0.8",
  "new_value": "0.95",
  "reason": "Reduce false positives per compliance team request",
  "timestamp": "2025-11-28T19:15:15.597579Z",
  "agent_id": "invoice-extractor-v2"
}
```

**Explanation:**
- `param_name`: Name of the parameter that changed
- `old_value`: Previous value (serialized as string)
- `new_value`: New value (serialized as string)
- `reason`: Why the change was made
- `timestamp`: When the change occurred
- `agent_id`: Which agent made the change

This is critical for compliance auditing - you can see exactly when and why parameters changed, and who made the change.

### RecordedEvent

A `RecordedEvent` is a wrapper that stores any type of event in a unified format for the event log.

**Code Definition:**

```python
class RecordedEvent(BaseModel):
    event_type: str
    timestamp: datetime
    data: dict[str, Any]
```

**Real Example from exported black box:**

```json
{
  "event_type": "parameter_substitution",
  "timestamp": "2025-11-28T19:15:15.597579Z",
  "data": {
    "param_name": "confidence_threshold",
    "old_value": "0.8",
    "new_value": "0.95",
    "reason": "Reduce false positives per compliance team request",
    "timestamp": "2025-11-28T19:15:15.597579Z",
    "agent_id": "invoice-extractor-v2"
  }
}
```

**Explanation:**
- `event_type`: Type of event (e.g., "task_plan", "collaborator_join", "parameter_substitution", "trace_step_start")
- `timestamp`: When the event was recorded
- `data`: The actual event data (varies by event type)

This wrapper allows all events to be stored in a single chronological list (`_all_events`) for easy replay and analysis.

---

## BlackBoxRecorder Class

The `BlackBoxRecorder` class is the main interface for recording workflow activities. Let's examine each method step by step.

### Initialization: `__init__`

**Code:**

```python
def __init__(self, workflow_id: str, storage_path: Path) -> None:
    if not isinstance(workflow_id, str):
        raise TypeError("workflow_id must be a string")
    if not isinstance(storage_path, Path):
        raise TypeError("storage_path must be a Path")
    if not workflow_id.strip():
        raise ValueError("workflow_id cannot be empty")

    self.workflow_id = workflow_id
    self.storage_path = storage_path
    self._recordings_path = storage_path / "black_box_recordings" / workflow_id

    # Ensure storage directory exists
    self._recordings_path.mkdir(parents=True, exist_ok=True)

    # In-memory stores for current session
    self._task_plans: dict[str, TaskPlan] = {}
    self._collaborators: dict[str, list[AgentInfo]] = {}
    self._parameter_subs: dict[str, list[ParameterSubstitution]] = {}
    self._execution_traces: dict[str, ExecutionTrace] = {}
    self._all_events: list[RecordedEvent] = []
```

**What it does:**
1. Validates inputs (workflow_id must be non-empty string, storage_path must be Path)
2. Sets up the storage directory structure: `{storage_path}/black_box_recordings/{workflow_id}/`
3. Creates the directory if it doesn't exist
4. Initializes in-memory dictionaries to store recordings for the current session

**Example Usage:**

```python
from pathlib import Path
from lesson_17.backend.explainability.black_box import BlackBoxRecorder

recorder = BlackBoxRecorder(
    workflow_id="invoice-processing-001",
    storage_path=Path("cache/")
)
# Creates: cache/black_box_recordings/invoice-processing-001/
```

### Recording Task Plans: `record_task_plan`

**Code:**

```python
def record_task_plan(self, task_id: str, plan: TaskPlan) -> None:
    # Validation...
    self._task_plans[task_id] = plan

    # Record as event
    event = RecordedEvent(
        event_type="task_plan",
        timestamp=datetime.now(UTC),
        data=plan.model_dump(mode="json"),
    )
    self._all_events.append(event)

    # Persist to disk
    self._persist_task_plan(task_id, plan)
```

**What it does:**
1. Validates inputs
2. Stores the plan in memory (`_task_plans` dictionary)
3. Creates a `RecordedEvent` wrapper and adds it to `_all_events`
4. Persists the plan to disk as `{task_id}_plan.json`

**Example Usage:**

```python
from datetime import UTC, datetime
from lesson_17.backend.explainability.black_box import TaskPlan, PlanStep

plan = TaskPlan(
    plan_id="plan-inv-001",
    task_id="task-extract-invoice",
    created_at=datetime.now(UTC),
    steps=[
        PlanStep(
            step_id="step-1-extract",
            description="Extract vendor and amount from invoice",
            agent_id="invoice-extractor",
            expected_inputs=["invoice_text"],
            expected_outputs=["vendor_name", "amount"],
            timeout_seconds=60,
            is_critical=True,
            order=1
        )
    ],
    dependencies={"step-2-validate": ["step-1-extract"]},
    rollback_points=["step-1-extract"]
)

recorder.record_task_plan("task-extract-invoice", plan)
# Saves to: cache/black_box_recordings/invoice-processing-001/task-extract-invoice_plan.json
```

### Recording Collaborators: `record_collaborators`

**Code:**

```python
def record_collaborators(self, task_id: str, agents: list[AgentInfo]) -> None:
    # Validation...
    self._collaborators[task_id] = agents

    # Record join events for each agent
    for agent in agents:
        event = RecordedEvent(
            event_type="collaborator_join",
            timestamp=agent.joined_at,
            data=agent.model_dump(mode="json"),
        )
        self._all_events.append(event)

    # Persist to disk
    self._persist_collaborators(task_id, agents)
```

**What it does:**
1. Validates inputs
2. Stores the collaborator list in memory
3. Creates a `collaborator_join` event for each agent and adds to `_all_events`
4. Persists to disk as `{task_id}_collaborators.json`

**Example Usage:**

```python
from lesson_17.backend.explainability.black_box import AgentInfo
from datetime import UTC, datetime

agents = [
    AgentInfo(
        agent_id="invoice-extractor-v2",
        agent_name="Invoice Extractor",
        role="extraction",
        joined_at=datetime.now(UTC),
        capabilities=["extraction", "ocr"]
    ),
    AgentInfo(
        agent_id="invoice-validator-v1",
        agent_name="Amount Validator",
        role="validation",
        joined_at=datetime.now(UTC),
        capabilities=["validation", "database_lookup"]
    )
]

recorder.record_collaborators("task-extract-invoice", agents)
# Saves to: cache/black_box_recordings/invoice-processing-001/task-extract-invoice_collaborators.json
```

### Recording Parameter Substitutions: `record_parameter_substitution`

**Code:**

```python
def record_parameter_substitution(
    self,
    task_id: str,
    param: str,
    old_val: Any,
    new_val: Any,
    reason: str,
    agent_id: str | None = None,
) -> None:
    # Validation...
    
    substitution = ParameterSubstitution(
        param_name=param,
        old_value=str(old_val),
        new_value=str(new_val),
        reason=reason,
        agent_id=agent_id,
    )

    if task_id not in self._parameter_subs:
        self._parameter_subs[task_id] = []
    self._parameter_subs[task_id].append(substitution)

    # Record as event
    event = RecordedEvent(
        event_type="parameter_substitution",
        timestamp=substitution.timestamp,
        data=substitution.model_dump(mode="json"),
    )
    self._all_events.append(event)

    # Persist to disk
    self._persist_parameter_substitutions(task_id)
```

**What it does:**
1. Validates inputs
2. Creates a `ParameterSubstitution` object
3. Appends it to the task's parameter substitution list
4. Creates a `RecordedEvent` and adds to `_all_events`
5. Persists all parameter substitutions for the task to disk as `{task_id}_params.json`

**Example Usage:**

```python
recorder.record_parameter_substitution(
    task_id="task-extract-invoice",
    param="confidence_threshold",
    old_val=0.8,
    new_val=0.95,
    reason="Reduce false positives per compliance team request",
    agent_id="invoice-extractor-v2"
)
# Saves to: cache/black_box_recordings/invoice-processing-001/task-extract-invoice_params.json
```

### Recording Execution Traces: `record_execution_trace`

**Code:**

```python
def record_execution_trace(self, task_id: str, trace: ExecutionTrace) -> None:
    # Validation...
    self._execution_traces[task_id] = trace

    # Record trace events
    for trace_event in trace.events:
        event = RecordedEvent(
            event_type=f"trace_{trace_event.event_type.value}",
            timestamp=trace_event.timestamp,
            data=trace_event.model_dump(mode="json"),
        )
        self._all_events.append(event)

    # Persist to disk
    self._persist_execution_trace(task_id, trace)
```

**What it does:**
1. Validates inputs
2. Stores the trace in memory
3. Wraps each `TraceEvent` in the trace as a `RecordedEvent` and adds to `_all_events`
4. Persists the complete trace to disk as `{task_id}_trace.json`

**Example Usage:**

```python
from lesson_17.backend.explainability.black_box import ExecutionTrace, TraceEvent, EventType
from datetime import UTC, datetime

trace = ExecutionTrace(
    trace_id="trace-invoice-processing-001",
    task_id="invoice-processing-001",
    start_time=datetime.now(UTC),
    events=[
        TraceEvent(
            event_id="evt-001",
            timestamp=datetime.now(UTC),
            event_type=EventType.STEP_START,
            agent_id="invoice-extractor-v2",
            step_id="extract_vendor"
        ),
        # ... more events ...
    ],
    final_outcome="failed",
    error_chain=["Cascade failure: validator crashed after parameter change"]
)

recorder.record_execution_trace("task-extract-invoice", trace)
# Saves to: cache/black_box_recordings/invoice-processing-001/task-extract-invoice_trace.json
```

### Adding Individual Trace Events: `add_trace_event`

**Code:**

```python
def add_trace_event(self, task_id: str, event: TraceEvent) -> None:
    # Validation...
    
    if task_id not in self._execution_traces:
        # Create new trace if doesn't exist
        self._execution_traces[task_id] = ExecutionTrace(
            trace_id=f"trace-{task_id}-{datetime.now(UTC).isoformat()}",
            task_id=task_id,
        )

    self._execution_traces[task_id].events.append(event)

    # Record as event
    recorded = RecordedEvent(
        event_type=f"trace_{event.event_type.value}",
        timestamp=event.timestamp,
        data=event.model_dump(mode="json"),
    )
    self._all_events.append(recorded)

    # Persist to disk
    self._persist_execution_trace(task_id, self._execution_traces[task_id])
```

**What it does:**
1. Validates inputs
2. Creates a new `ExecutionTrace` if one doesn't exist for the task
3. Appends the event to the trace's events list
4. Wraps it as a `RecordedEvent` and adds to `_all_events`
5. Persists the updated trace to disk

**Example Usage:**

```python
event = TraceEvent(
    event_id="evt-014",
    timestamp=datetime.now(UTC),
    event_type=EventType.CHECKPOINT,
    agent_id="invoice-extractor-v2",
    step_id="extract_vendor",
    metadata={"checkpoint_id": "chk-002", "state": {"progress": 0.5}}
)

recorder.add_trace_event("task-extract-invoice", event)
# Updates: cache/black_box_recordings/invoice-processing-001/task-extract-invoice_trace.json
```

### Exporting Black Box: `export_black_box`

**Code:**

```python
def export_black_box(self, task_id: str, filepath: Path) -> None:
    # Validation...
    
    export_data = {
        "workflow_id": self.workflow_id,
        "task_id": task_id,
        "exported_at": datetime.now(UTC).isoformat(),
        "task_plan": (
            self._task_plans[task_id].model_dump(mode="json")
            if task_id in self._task_plans
            else None
        ),
        "collaborators": (
            [a.model_dump(mode="json") for a in self._collaborators[task_id]]
            if task_id in self._collaborators
            else []
        ),
        "parameter_substitutions": (
            [s.model_dump(mode="json") for s in self._parameter_subs[task_id]]
            if task_id in self._parameter_subs
            else []
        ),
        "execution_trace": (
            self._execution_traces[task_id].model_dump(mode="json")
            if task_id in self._execution_traces
            else None
        ),
        "all_events": [e.model_dump(mode="json") for e in self._all_events],
    }

    # Ensure parent directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w") as f:
        json.dump(export_data, f, indent=2, default=str)
```

**What it does:**
1. Validates inputs
2. Collects all recorded data for the task (plan, collaborators, parameter substitutions, trace)
3. Includes all events in chronological order
4. Writes everything to a single JSON file

**Example Usage:**

```python
recorder.export_black_box(
    task_id="task-extract-invoice",
    filepath=Path("cache/exports/task-extract-invoice-blackbox.json")
)
# Creates: cache/exports/task-extract-invoice-blackbox.json
```

### Replaying Events: `replay`

**Code:**

```python
def replay(self, task_id: str) -> Iterator[RecordedEvent]:
    # Validation...
    
    # Load from disk if not in memory
    self._load_from_disk(task_id)

    # Sort all events by timestamp
    sorted_events = sorted(self._all_events, key=lambda e: e.timestamp)

    for event in sorted_events:
        yield event
```

**What it does:**
1. Validates inputs
2. Loads any missing data from disk
3. Sorts all events chronologically
4. Yields events one by one in order

**Example Usage:**

```python
for event in recorder.replay("task-extract-invoice"):
    print(f"{event.timestamp}: {event.event_type}")
    # Output:
    # 2025-11-28T19:15:15.583528Z: task_plan
    # 2025-11-27T14:00:00Z: collaborator_join
    # 2025-11-27T14:00:00Z: trace_step_start
    # ...
```

### Helper Methods

#### `compute_hash`

Computes SHA256 hash of data for integrity verification:

```python
@staticmethod
def compute_hash(data: Any) -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
```

#### Persistence Methods

Private methods that handle disk I/O:

- `_persist_task_plan`: Saves plan to `{task_id}_plan.json`
- `_persist_collaborators`: Saves collaborators to `{task_id}_collaborators.json`
- `_persist_parameter_substitutions`: Saves parameter substitutions to `{task_id}_params.json`
- `_persist_execution_trace`: Saves trace to `{task_id}_trace.json`
- `_load_from_disk`: Loads all recordings for a task from disk

---

## Complete Data Flow Example

Let's walk through a complete workflow example showing how data flows through the black box recorder.

### Step 1: Initialize Recorder

```python
from pathlib import Path
from lesson_17.backend.explainability.black_box import BlackBoxRecorder

recorder = BlackBoxRecorder(
    workflow_id="invoice-processing-001",
    storage_path=Path("cache/")
)
```

**Result:**
- Creates directory: `cache/black_box_recordings/invoice-processing-001/`
- Initializes empty in-memory stores

### Step 2: Record Task Plan

```python
from lesson_17.backend.explainability.black_box import TaskPlan, PlanStep
from datetime import UTC, datetime

plan = TaskPlan(
    plan_id="plan-inv-001",
    task_id="task-extract-invoice",
    created_at=datetime.now(UTC),
    steps=[
        PlanStep(
            step_id="step-1-extract",
            description="Extract vendor and amount from invoice",
            agent_id="invoice-extractor",
            expected_inputs=["invoice_text"],
            expected_outputs=["vendor_name", "amount"],
            timeout_seconds=60,
            is_critical=True,
            order=1
        ),
        PlanStep(
            step_id="step-2-validate",
            description="Validate extracted data against database",
            agent_id="data-validator",
            expected_inputs=["vendor_name", "amount"],
            expected_outputs=["validation_result", "vendor_id"],
            timeout_seconds=30,
            is_critical=True,
            order=2
        )
    ],
    dependencies={"step-2-validate": ["step-1-extract"]},
    rollback_points=["step-1-extract"]
)

recorder.record_task_plan("task-extract-invoice", plan)
```

**Result:**
- Stores plan in `_task_plans["task-extract-invoice"]`
- Creates `RecordedEvent` with `event_type="task_plan"` and adds to `_all_events`
- Saves to: `cache/black_box_recordings/invoice-processing-001/task-extract-invoice_plan.json`

**File Created (`task-extract-invoice_plan.json`):**
```json
{
  "plan_id": "plan-inv-001",
  "task_id": "task-extract-invoice",
  "created_at": "2025-11-28T19:15:15.583451Z",
  "steps": [
    {
      "step_id": "step-1-extract",
      "description": "Extract vendor and amount from invoice",
      "agent_id": "invoice-extractor",
      "expected_inputs": ["invoice_text"],
      "expected_outputs": ["vendor_name", "amount"],
      "timeout_seconds": 60,
      "is_critical": true,
      "order": 1
    },
    {
      "step_id": "step-2-validate",
      "description": "Validate extracted data against database",
      "agent_id": "data-validator",
      "expected_inputs": ["vendor_name", "amount"],
      "expected_outputs": ["validation_result", "vendor_id"],
      "timeout_seconds": 30,
      "is_critical": true,
      "order": 2
    }
  ],
  "dependencies": {
    "step-2-validate": ["step-1-extract"]
  },
  "rollback_points": ["step-1-extract"],
  "metadata": {}
}
```

### Step 3: Record Collaborators

```python
from lesson_17.backend.explainability.black_box import AgentInfo

agents = [
    AgentInfo(
        agent_id="invoice-extractor-v2",
        agent_name="Invoice Extractor",
        role="extraction",
        joined_at=datetime(2025, 11, 27, 14, 0, 0, tzinfo=UTC),
        capabilities=["extraction", "ocr"]
    ),
    AgentInfo(
        agent_id="invoice-validator-v1",
        agent_name="Amount Validator",
        role="validation",
        joined_at=datetime(2025, 11, 27, 14, 0, 12, tzinfo=UTC),
        capabilities=["validation", "database_lookup"]
    )
]

recorder.record_collaborators("task-extract-invoice", agents)
```

**Result:**
- Stores collaborators in `_collaborators["task-extract-invoice"]`
- Creates two `RecordedEvent` objects with `event_type="collaborator_join"` and adds to `_all_events`
- Saves to: `cache/black_box_recordings/invoice-processing-001/task-extract-invoice_collaborators.json`

**File Created (`task-extract-invoice_collaborators.json`):**
```json
[
  {
    "agent_id": "invoice-extractor-v2",
    "agent_name": "Invoice Extractor",
    "role": "extraction",
    "joined_at": "2025-11-27T14:00:00Z",
    "capabilities": ["extraction", "ocr"]
  },
  {
    "agent_id": "invoice-validator-v1",
    "agent_name": "Amount Validator",
    "role": "validation",
    "joined_at": "2025-11-27T14:00:12Z",
    "capabilities": ["validation", "database_lookup"]
  }
]
```

### Step 4: Record Parameter Substitution

```python
recorder.record_parameter_substitution(
    task_id="task-extract-invoice",
    param="confidence_threshold",
    old_val=0.8,
    new_val=0.95,
    reason="Reduce false positives per compliance team request",
    agent_id="invoice-extractor-v2"
)
```

**Result:**
- Creates `ParameterSubstitution` object
- Appends to `_parameter_subs["task-extract-invoice"]`
- Creates `RecordedEvent` with `event_type="parameter_substitution"` and adds to `_all_events`
- Saves to: `cache/black_box_recordings/invoice-processing-001/task-extract-invoice_params.json`

**File Created (`task-extract-invoice_params.json`):**
```json
[
  {
    "param_name": "confidence_threshold",
    "old_value": "0.8",
    "new_value": "0.95",
    "reason": "Reduce false positives per compliance team request",
    "timestamp": "2025-11-28T19:15:15.597579Z",
    "agent_id": "invoice-extractor-v2"
  }
]
```

### Step 5: Record Execution Trace

```python
from lesson_17.backend.explainability.black_box import ExecutionTrace, TraceEvent, EventType

trace = ExecutionTrace(
    trace_id="trace-invoice-processing-001",
    task_id="invoice-processing-001",
    start_time=datetime(2025, 11, 27, 14, 0, 0, tzinfo=UTC),
    end_time=datetime(2025, 11, 27, 14, 0, 18, tzinfo=UTC),
    events=[
        TraceEvent(
            event_id="evt-001",
            timestamp=datetime(2025, 11, 27, 14, 0, 0, tzinfo=UTC),
            event_type=EventType.STEP_START,
            agent_id="invoice-extractor-v2",
            step_id="extract_vendor"
        ),
        TraceEvent(
            event_id="evt-006",
            timestamp=datetime(2025, 11, 27, 14, 0, 12, tzinfo=UTC),
            event_type=EventType.STEP_END,
            agent_id="invoice-extractor-v2",
            step_id="extract_vendor",
            duration_ms=12000,
            metadata={"success": True, "confidence": 0.92}
        ),
        TraceEvent(
            event_id="evt-010",
            timestamp=datetime(2025, 11, 27, 14, 0, 15, tzinfo=UTC),
            event_type=EventType.ERROR,
            agent_id="invoice-validator-v1",
            step_id="validate_amount",
            metadata={
                "error_message": "Confidence threshold too high (0.95) - no valid results",
                "error_type": "ValidationError",
                "is_recoverable": False
            }
        )
    ],
    final_outcome="failed",
    error_chain=[
        "Cascade failure: validator crashed after parameter change",
        "Parameter substitution (confidence_threshold: 0.8 → 0.95) caused empty validation results"
    ]
)

recorder.record_execution_trace("task-extract-invoice", trace)
```

**Result:**
- Stores trace in `_execution_traces["task-extract-invoice"]`
- Wraps each `TraceEvent` as a `RecordedEvent` with `event_type="trace_{event_type}"` and adds to `_all_events`
- Saves to: `cache/black_box_recordings/invoice-processing-001/task-extract-invoice_trace.json`

**File Created (`task-extract-invoice_trace.json`):**
```json
{
  "trace_id": "trace-invoice-processing-001",
  "task_id": "invoice-processing-001",
  "start_time": "2025-11-27T14:00:00Z",
  "end_time": "2025-11-27T14:00:18Z",
  "events": [
    {
      "event_id": "evt-001",
      "timestamp": "2025-11-27T14:00:00Z",
      "event_type": "step_start",
      "agent_id": "invoice-extractor-v2",
      "step_id": "extract_vendor",
      "input_hash": null,
      "output_hash": null,
      "duration_ms": null,
      "metadata": {}
    },
    // ... more events ...
  ],
  "final_outcome": "failed",
  "error_chain": [
    "Cascade failure: validator crashed after parameter change",
    "Parameter substitution (confidence_threshold: 0.8 → 0.95) caused empty validation results"
  ]
}
```

### Step 6: Export Black Box

```python
recorder.export_black_box(
    task_id="task-extract-invoice",
    filepath=Path("cache/exports/task-extract-invoice-blackbox.json")
)
```

**Result:**
- Collects all data for the task
- Combines into a single JSON file
- Saves to: `cache/exports/task-extract-invoice-blackbox.json`

**File Created (`task-extract-invoice-blackbox.json`):**
```json
{
  "workflow_id": "invoice-processing-001",
  "task_id": "task-extract-invoice",
  "exported_at": "2025-11-28T19:15:15.617451+00:00",
  "task_plan": { /* ... plan data ... */ },
  "collaborators": [ /* ... collaborator data ... */ ],
  "parameter_substitutions": [ /* ... parameter substitution data ... */ ],
  "execution_trace": { /* ... trace data ... */ },
  "all_events": [ /* ... all events in chronological order ... */ ]
}
```

---

## Real-World Example: Invoice Processing Cascade Failure

Let's analyze the real invoice processing example to see how the black box captured a cascade failure.

### The Scenario

An invoice processing workflow failed due to a parameter change that caused a cascade failure. The black box captured the entire sequence of events.

### Timeline of Events

**14:00:00 - Workflow Starts**
- `invoice-extractor-v2` starts extracting vendor information
- Agent joins the workflow

**14:00:05 - Decision Point**
- Agent decides to use GPT-4 for OCR correction (instead of GPT-3.5, Claude, or rule-based)
- Rationale: "Higher accuracy needed for noisy scans"

**14:00:10 - Parameter Change (Critical Moment)**
- `confidence_threshold` changed from `0.8` to `0.95`
- Reason: "Reduce false positives per compliance team request"
- This change was recorded in `task-extract-invoice_params.json`

**14:00:11 - Checkpoint**
- Checkpoint saved with state: `{"vendor_name": "Acme Corp", "amount": 4523.5}`

**14:00:12 - Step 1 Completes**
- Extraction step ends successfully
- Duration: 12 seconds
- Confidence: 0.92 (below the new threshold of 0.95!)

**14:00:12 - Step 2 Starts**
- `invoice-validator-v1` starts validation
- Agent joins the workflow

**14:00:15 - Error Occurs**
- Validation fails with error: "Confidence threshold too high (0.95) - no valid results"
- The extracted data had confidence 0.92, which is below the new threshold of 0.95
- Error type: `ValidationError`
- Not recoverable

**14:00:18 - Step 2 Fails**
- Validation step ends with failure
- Duration: 6 seconds
- Failure reason: "threshold_exceeded"

**Later - Rollback**
- Workflow orchestrator detects cascade failure
- Rolls back to `extract_vendor` step
- Recovery action: "Retry with original parameters"

### How the Black Box Captured This

#### 1. Parameter Substitution Record

The parameter change was captured in `task-extract-invoice_params.json`:

```json
{
  "param_name": "confidence_threshold",
  "old_value": "0.8",
  "new_value": "0.95",
  "reason": "Reduce false positives per compliance team request",
  "timestamp": "2025-11-28T19:15:15.597579Z",
  "agent_id": "invoice-extractor-v2"
}
```

This shows:
- **What changed**: `confidence_threshold`
- **From/To**: `0.8` → `0.95`
- **Why**: Compliance team request
- **Who**: `invoice-extractor-v2`
- **When**: During execution

#### 2. Execution Trace Events

The trace captured the sequence of events:

**Event evt-004: Parameter Change**
```json
{
  "event_id": "evt-004",
  "timestamp": "2025-11-27T14:00:10Z",
  "event_type": "parameter_change",
  "agent_id": "invoice-extractor-v2",
  "step_id": "extract_vendor",
  "metadata": {
    "parameter": "confidence_threshold",
    "old_value": 0.8,
    "new_value": 0.95
  }
}
```

**Event evt-006: Step End (Success)**
```json
{
  "event_id": "evt-006",
  "timestamp": "2025-11-27T14:00:12Z",
  "event_type": "step_end",
  "agent_id": "invoice-extractor-v2",
  "step_id": "extract_vendor",
  "duration_ms": 12000,
  "metadata": {
    "success": true,
    "confidence": 0.92  // Below new threshold!
  }
}
```

**Event evt-010: Error**
```json
{
  "event_id": "evt-010",
  "timestamp": "2025-11-27T14:00:15Z",
  "event_type": "error",
  "agent_id": "invoice-validator-v1",
  "step_id": "validate_amount",
  "metadata": {
    "error_message": "Confidence threshold too high (0.95) - no valid results",
    "error_type": "ValidationError",
    "is_recoverable": false
  }
}
```

#### 3. Error Chain

The trace captured the error chain showing how the failure cascaded:

```json
{
  "final_outcome": "failed",
  "error_chain": [
    "Cascade failure: validator crashed after parameter change",
    "Parameter substitution (confidence_threshold: 0.8 → 0.95) caused empty validation results"
  ]
}
```

This clearly shows:
1. The parameter change happened
2. It caused the validator to fail
3. The failure cascaded through the workflow

#### 4. Rollback Point

The trace captured the rollback event:

```json
{
  "event_id": "evt-013",
  "timestamp": "2025-11-28T19:15:15.611818Z",
  "event_type": "rollback",
  "agent_id": "workflow-orchestrator",
  "step_id": "extract_vendor",
  "metadata": {
    "rollback_reason": "Cascade failure detected",
    "rollback_to": "extract_vendor",
    "steps_rolled_back": ["validate_amount"],
    "recovery_action": "Retry with original parameters"
  }
}
```

### Analysis Insights

From the black box data, we can see:

1. **Root Cause**: Parameter change from 0.8 to 0.95
2. **Immediate Effect**: Extraction completed with confidence 0.92 (below new threshold)
3. **Cascade**: Validator failed because no results met the threshold
4. **Recovery**: System rolled back to extraction step to retry with original parameters

### Why This Matters

Without the black box recorder:
- You'd see "validation failed" but not know why
- You wouldn't know a parameter changed during execution
- You couldn't trace the cascade failure
- You couldn't audit who changed what and why

With the black box recorder:
- Complete audit trail of parameter changes
- Clear error chain showing cascade failure
- Timestamped events showing exact sequence
- Rollback points for recovery
- Compliance-ready records of all changes

---

## Summary

The `BlackBoxRecorder` provides comprehensive recording of agent workflow activities:

1. **Task Plans**: Capture what was supposed to happen
2. **Collaborators**: Track which agents participated
3. **Parameter Substitutions**: Audit all parameter changes with reasons
4. **Execution Traces**: Record everything that actually happened
5. **Event Replay**: Replay events chronologically for debugging

This enables:
- **Post-incident analysis**: Understand exactly what happened
- **Compliance auditing**: Complete records of all changes
- **Cascade failure investigation**: Trace how failures propagate
- **Workflow optimization**: Analyze execution patterns

The black box recorder is your "flight recorder" for agent workflows, ensuring you always have a complete record of what happened, when it happened, and why it happened.
