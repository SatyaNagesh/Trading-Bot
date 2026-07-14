# QuantLab AI — Task Orchestration Engine

> **How Work Gets Done**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Task Orchestration Engine (TOE) is responsible for decomposing high-level goals into executable tasks, assigning them to capable agents, managing dependencies, and tracking completion.

---

## Core Concepts

### Task
A unit of work assigned to a single agent:
```yaml
task_id: task_001
type: research | strategy | validation | execution | support
status: pending | assigned | in_progress | completed | failed | cancelled
priority: critical | high | normal | low
assigned_to: agent_id
depends_on: [task_id, ...]
created_at: timestamp
deadline: timestamp
completion_criteria: string
```

### Workflow
A directed acyclic graph (DAG) of tasks:
```yaml
workflow_id: wf_001
name: "Research new strategy"
tasks:
  - task_001: "Gather market data"
  - task_002: "Formulate hypothesis"
  - task_003: "Design strategy"
  - task_004: "Implement backtest"
dependencies:
  task_002: [task_001]
  task_003: [task_002]
  task_004: [task_003]
```

### Job
A top-level request that generates a workflow:
```yaml
job_id: job_001
type: research_request
request: "Find mean reversion opportunities in NSE midcaps"
status: active
workflow_id: wf_001
```

---

## Task Lifecycle

```
Created ──► Pending ──► Assigned ──► In Progress ──► Completed
                │           │              │
                ▼           ▼              ▼
            Cancelled   Reassigned      Failed
```

---

## Orchestration Process

### 1. Request Intake
```
Human/Agent → Job Request → TOE
```
- Validate request format
- Classify request type
- Create job record

### 2. Decomposition
```
TOE → Decomposition → Task DAG
```
- Break job into atomic tasks
- Determine dependencies
- Assign priority levels
- Set deadlines

### 3. Assignment
```
TOE → Agent Registry → Task Assignment
```
- Find capable agents
- Check agent availability
- Load-balance assignments
- Consider agent specialization

### 4. Execution Monitoring
```
TOE → Active Task Monitoring
```
- Track progress
- Handle timeouts
- Detect failures
- Manage reassignments

### 5. Completion
```
TOE → Workflow Completion
```
- Verify completion criteria
- Aggregate results
- Report to requester
- Archive workflow

---

## Task Routing Algorithm

```python
def assign_task(task, available_agents):
    candidates = [
        agent for agent in available_agents
        if task.type in agent.capabilities
        and agent.current_load < agent.max_load
    ]
    
    if not candidates:
        return escalate(task)
    
    # Score candidates
    scored = [
        (agent, calculate_score(agent, task))
        for agent in candidates
    ]
    
    # Select best candidate
    selected = max(scored, key=lambda x: x[1])
    return selected[0]

def calculate_score(agent, task):
    return (
        specialization_bonus(agent, task) * 0.4 +
        availability_score(agent) * 0.3 +
        past_performance_score(agent, task.type) * 0.2 +
        load_balancing_score(agent) * 0.1
    )
```

---

## Dependency Resolution

### Dependency Types
| Type | Behavior | Example |
|------|----------|---------|
| blocks | Task B cannot start until A completes | Data before analysis |
| requires | Task B needs output from A | Hypothesis before strategy |
| optional | Task B can start without A | Documentation alongside |
| notification | Inform A when B completes | Status updates |

### Cycle Detection
All workflows are validated as DAGs before execution:
- Topological sort on creation
- Cycle detection on modification
- Automatic deadlock prevention

---

## Failure Handling

### Failure Types
| Type | Action | Recovery |
|------|--------|----------|
| Agent failure | Reassign task | Automatic |
| Timeout | Escalate priority | Manual review |
| Validation failure | Return to design | Iterative |
| Resource exhaustion | Queue task | Auto-retry |

### Retry Policy
```yaml
retry_policy:
  max_retries: 3
  backoff: exponential
  initial_delay: 60s
  max_delay: 3600s
  retryable_errors:
    - TIMEOUT
    - RESOURCE_EXHAUSTED
    - TRANSIENT_ERROR
```

---

## Task Priorities

### Priority-Based Scheduling
```yaml
critical:
  preempts: true
  max_concurrent: 1
  SLA: 30s
high:
  preempts: normal
  max_concurrent: 3
  SLA: 5m
normal:
  preempts: low
  max_concurrent: 10
  SLA: 1h
low:
  preempts: false
  max_concurrent: unlimited
  SLA: 24h
```

---

## Performance Monitoring

### TOE Metrics
| Metric | Description | Target |
|--------|-------------|--------|
| Task throughput | Tasks completed per minute | > 10/min |
| Queue depth | Pending tasks | < 100 |
| Average wait time | Time in queue | < 30s |
| Assignment accuracy | Right agent for task | > 95% |
| Failure rate | Failed / total tasks | < 5% |

---

## API

### Internal API
```
POST   /orchestrator/jobs           # Create new job
GET    /orchestrator/jobs/{id}      # Get job status
POST   /orchestrator/tasks          # Create single task
GET    /orchestrator/tasks/{id}     # Get task status
POST   /orchestrator/tasks/{id}/cancel  # Cancel task
GET    /orchestrator/workflows/{id} # Get workflow status
POST   /orchestrator/reassign       # Force reassign
```
