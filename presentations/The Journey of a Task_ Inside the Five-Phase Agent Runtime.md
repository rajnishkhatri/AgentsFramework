### The Journey of a Task: Inside the Five-Phase Agent Runtime

**Executive Overview: The Five-Phase Framework**To build truly autonomous systems, we must move beyond the "black box" mentality of simple input-output loops. This runtime is architected as a  **LangGraph StateGraph** , a structured orchestration layer that ensures every task undergoes a rigorous five-phase journey. By transitioning from a "brittle" ReAct loop to a tiered reasoning framework, the system provides deterministic safety gates, strategic depth selection, and self-correcting evaluation loops.| Phase | Primary Intent | Key Node || \------ | \------ | \------ || **1\. Ingress** | Block unsafe or malicious input at Step 0\. | guard\_input || **2\. Planning** | Determine depth and build a deterministic plan floor. | route\_node || **3\. Execution** | Execute via the T0 ReAct spine or T3 Supervisor fan-out. | call\_llm / supervisor || **4\. Evaluation** | Score outcomes via GoalJudge; trigger T2 Reflexion if needed. | evaluate\_node || **5\. Exit** | Synthesize the reasoning journey for the final UI recap. | reasoning\_recap |  
**Why this structure matters:**  A standard "Input-Output" approach is inherently fragile; if the LLM fails to reason correctly on the first pass, the task fails. This five-phase framework introduces "thinking before acting" (Planning) and "quality control" (Evaluation). More importantly, it provides a  **deterministic floor** —a baseline of logic that ensures the agent remains reliable even when probabilistic LLM outputs vary.*This journey begins at the Ingress stage, where the system acts as a high-fidelity gatekeeper for the entire pipeline.*

##### Phase 1: Ingress (The Gatekeeper)

Before the system consumes "expensive brainpower" or valuable LLM tokens, the guard\_input node serves as the primary  **InputGuardrail** . This node operates exclusively at  **Step 0**  of the task journey to determine if a request is acceptable for processing.The accept/reject mechanism is the system’s first line of defense. By utilizing InputGuardrail.is\_acceptable(), the runtime ensures that malicious, out-of-scope, or unsafe prompts are neutralized before they can influence the planning or execution phases. This logic is driven by a specialized prompt template (input\_guardrail.j2) which directs the system’s judging layers.**Specific Safety Checks:**

* **LLM Judge:**  A high-speed model that evaluates the prompt against constitutional safety guidelines.  
* **ONNX Classifier:**  An optional, low-latency machine learning model used to categorize and filter input with high efficiency.*Once a task is "accepted," it moves from the safety gate to the strategic planning center, where its roadmap is defined.*

##### Phase 2: Planning (The Blueprint)

In the shipped architectural code, the  **route\_node**  serves as the central intelligence hub; there is no separate "planner" node. Instead, the route\_node handles both "Planning Depth" selection and the construction of the task's strategic artifacts.The system first establishes a  **deterministic floor**  using build\_plan\_artifact. This ensures that even if the PlanGenerator LLM fails to provide a valid roadmap, the system has a baseline plan to execute. Only after this floor is established does the system attempt to enhance the plan with LLM-generated insights.| Depth Level | Step Budget | Selection Logic | Instructional Strictness || \------ | \------ | \------ | \------ || **L0 (Minimal)** | 1 | Simple tasks or post-tool synthesis. | Concise synthesis; proceed directly. || **L1 (Moderate)** | 3 | Complexity score \>= 2; tasks \>= 25 words. | Outline 2–4 concrete steps; execute in order. || **L2 (Deep)** | 5 | Complexity score \>= 3; incident-narrative markers. | Multi-step plan; state assumptions; validate results. |  
**The T1 Plan Artifact & Task Understanding:**  Before moving to action, the system generates a  **Task Understanding**  component. This restates the user's intent and defines explicit "Success Conditions." By establishing these metrics upfront, the system creates a quantifiable yardstick for Phase 4 (Evaluation).*With the finalized plan in hand, the StateGraph determines whether the task requires a direct path or complex delegation.*

##### Phase 3: Execution (The Action Path)

Execution is handled through two orthogonal routes. The choice depends on the complexity identified in Phase 2 and the configuration of the runtime.**Path A: The T0 ReAct Spine**  This is the standard execution loop. The agent enters a cycle of call\_llm and execute\_tool, following a linear progression until the plan steps are satisfied or a final answer is reached.**Path B: T3 Supervisor Fan-out (Parallel Execution)**  For high-complexity tasks, the system can parallelize work. This path is only triggered if  **all**  of the following conditions are met:

1. t3\_fanout\_enabled is set to True.  
2. The Planning Depth is  **L1**  or  **L2** .  
3. The plan contains at least  **two steps**  that pass the  **validate\_independence**  **(GAIA guard)**  check.**Roles in the Fan-out Subgraph:**  
* **Supervisor:**  Decomposes the plan into independent branches, ensuring no sequential dependencies exist between workers.  
* **Worker:**  Executes specific branch objectives in isolation.  
* **Join:**  A synthesizer that gathers all results. Crucially,  **worker\_results**  uses an  **operator.add**  **reducer** , allowing parallel outputs to accumulate into a single state without data loss.*All execution paths eventually converge at the evaluation stage to ensure the results meet the pre-defined success conditions.*

##### Phase 4: Evaluation (The Quality Control)

Phase 4 is governed by the evaluate\_node, where the  **GoalJudge**  compares the execution results against the TaskUnderstanding artifacts.**The T2 Reflexion Loop**  If the GoalJudge finds the outcome lacking, the system initiates "Reflexion." This allows the agent to critique its own work—utilizing the  **T2 Reflexion semantic gradient** —and re-enter the planning/execution phase. Even  **L0 tasks**  can trigger this loop if the initial response is insufficient. The decision to continue is triggered by:

1. **Failed/Partial Outcomes:**  Success conditions from Phase 2 were not met.  
2. **D3 Prose Thrash:**  The agent is spinning its wheels (detected via classify\_no\_progress as prose\_repeat).  
3. **Remaining Budget:**  The task has not exceeded the max\_reflexion\_attempts.**The Synthesis Validator**  This validator applies depth-aware rules to the final synthesis. For L1 and L2 tasks, it strictly checks for "open todos" in the plan. For L2 tasks specifically, it enforces a  **"Branch coverage \< 60%"**  rule, failing any task that ignores significant portions of the parallelized plan.*Once the answer is verified or the budget is exhausted, the system transitions to its final summary.*

##### Phase 5: Exit (The Reasoning Recap)

The final phase, handled by the reasoning\_recap node, is designed for human-centric explainability. It synthesizes the tool results, planning artifacts, and any reflections into a human-readable  **Reasoning Summary**  for the UI.**Final Task States:**

* **END:**  The task is successfully completed, and a verified answer is provided.  
* **Escalation:**  The task failed to meet success conditions, and the reflexion budget is exhausted.**Master Key: State Key Reference**| State Key | Purpose || \------ | \------ || planning\_depth | Memos the chosen complexity level (L0, L1, or L2) for the task. || plan\_artifact | Stores the roadmap, including the deterministic floor and ordered steps. || reflections | An append-only history of critiques used to drive the T2 reasoning gradient. || last\_task\_outcome | The primary carrier that dictates whether the system should END or escalate. || reasoning\_summary | The final human-readable synthesis of the agent's internal logic. |

##### Final Insight

By utilizing this Five-Phase Framework, we transform the agent from a probabilistic "guessing" engine into a  **trusted autonomous system** . Through the use of deterministic plan floors, GAIA-guarded parallelization, and depth-aware evaluation, the runtime ensures that every task journey is safe, strategic, and—most importantly—verifiable.  
