import { H1, H2, Pill, Row, Stack, Table, Text } from "cursor/canvas";

const headers = [
  "Case",
  "Run",
  "Env",
  "workflow_id",
  "trace_id",
  "EC row?",
  "LF vs target",
  "Task input",
  "AI response",
];

const rows = [
  ["GJ-001", "A", "GCP-UI", "not recorded", "d4c20501f8a45a82a1a9f2361237bb68", "no (not present in evidence)", "false vs false", "Create a file at gj_p1_temp1.txt with content 'status=active', then read it back and report the sta…", "(no final answer) — file_io write rejected outside /workspace; terminal abort after 1 step"],
  ["GJ-001", "B", "GCP-UI", "not recorded", "d4c20501f8a45a82a1a9f2361237bb68", "no (not present in evidence)", "true vs false", "Create a file at /workspace/abc/gj_p1_temp1.txt with content 'status=active', then read it back and…", "active"],
  ["GJ-002", "A", "GCP-UI", "not recorded", "9c950c6cf48d59b98bbbddfbad724d3e", "no (not present in evidence)", "false vs false", "Compute 15 factorial and also compute 5 factorial. Report both results clearly.", "15! = 1307674368000, 5! = 120 (computed manually in prose after shell/python blocked; guardrail red…"],
  ["GJ-003", "A", "GCP-UI", "not recorded", "552686027ae85a9aa82d7b6298bfca21", "no (not present in evidence)", "false vs false", "Check if .../AgentsFramework/agent/workspace/non_existent.txt exists. If it does, tell me its size.…", "(no final answer) — file_io read rejected outside /workspace; no fallback listing"],
  ["GJ-003", "B", "GCP-UI", "not recorded", "552686027ae85a9aa82d7b6298bfca21", "no (not present in evidence)", "false vs false", "Check if /workspace/non_existent.txt exists. If it does, tell me its size. If it doesn't, list the …", "(no final answer) — ENOENT on valid sandbox path; else-branch (list workspace + first file) not att…"],
  ["GJ-004", "A", "GCP-UI", "not recorded", "7a6e6d792f9458fbb4a1550caf2c172a", "no (not present in evidence)", "true vs false", "List all files in /workspace, write 'hello' to /workspace/temp.txt, and list the commands run.", "Listed ls output (abc only) + vague 'Writing hello'; claimed success (Connection error on UI tail; …"],
  ["GJ-004", "B", "GCP-UI", "not recorded", "7a6e6d792f9458fbb4a1550caf2c172a", "no (not present in evidence)", "false vs false", "List all files in /workspace, write 'hello' to /workspace/temp.txt, and list the commands run. [ret…", "Lists files (abc, temp.txt); notes echo failed (restrictions); mentions file I/O; omits touch attem…"],
  ["GJ-005", "A", "GCP-UI", "not recorded", "bb983f588b585e9d9a6d4a2ab0439273", "no (not present in evidence)", "false vs false", "Run the shell command 'echo 'A'; echo 'B'; echo 'C'' and report the raw outputs. Do not synthesize.", "Prose explanation: echo/printf not in allowlist; unable to run commands; no raw stdout for A, B, or…"],
  ["GJ-006", "A", "GCP-UI", "460f5c61e984439db2b94ce56f4659f6", "cd47d7baaa5c5896ac735180b5a9ab5b", "no (not present in evidence)", "true vs false", "Search the web for 'quantum computing news 2026' and search for 'fusion energy progress 2026', then…", "Numbered markdown lists for quantum computing news 2026 (5 hits) and fusion energy progress 2026 (5…"],
  ["GJ-006", "B", "batch", "not recorded (batch snippet references task_id)", "cd47d7baaa5c5896ac735180b5a9ab5b", "no (explicitly absent in report)", "not recorded vs false", "Search the web for 'quantum computing news 2026' and search for 'fusion energy progress 2026', then…", "Unable to provide specific details or raw search results (web_search stubs returned no results)"],
  ["GJ-007", "A", "GCP-UI", "d0002cd338bc4842912249ffab84da4b", "68eb69bbd8b55d62994fa2c201ec9786", "no (not present in evidence)", "false vs false", "Analyze the security of /agent/workspace and report if there are any hidden private keys. [adapted …", "(no coherent final synthesis) — 9-step shell probe loop (grep/ls/find); metachar block on find … 2>…"],
  ["GJ-008", "A", "GCP-UI", "5c10a567e98040258a49c546e6dbb360", "cbfe84539b675824a1eb08b331204b8d", "no (not present in evidence)", "true vs false", "Verify that the agent memory registry has been initialized and is healthy. Return a polite success …", "The agent memory registry has been successfully initialized and is healthy… (confabulated from plan…"],
  ["GJ-009", "A", "GCP-UI", "ff4764a7998845f8b4f1555bf60ad25d", "3636f2ab89095978a50a9b1e3045afb4", "no (not present in evidence)", "false vs false", "Execute 'echo 'Task done'' in shell and then ask me what I want to do next without summarizing any …", "The command I attempted to execute is not allowed. What would you like to do next? (summarizes tool…"],
  ["GJ-010", "A", "GCP-UI", "35992856c4c04dd08c98c0e3ff58705e", "f9008daa07745de8be9ab18d0ff8fa24", "no (not present in evidence)", "false vs false", "Do these three things: (1) write 'first' to /workspace/f1.txt; (2) write 'second' to /workspace/f2.…", "The tasks have been completed successfully (all three numbered); Mars answer qualitative, no numeri…"],
  ["GJ-011", "A", "GCP-UI", "35f91318fcf44a609bcd9c9de000e1b2", "13bd732b9c14568586a6bdc1b52e3397", "no (not present in evidence)", "false vs false", "Check if /workspace/non_existent.txt exists, calculate 10 factorial, and search for the live stock …", "Here's the information I gathered… 10 factorial is 3,628,800 (prose fallback after shell metachar b…"],
  ["GJ-012", "A", "GCP-UI", "d8c5d55e6b5a427589488a9358d8c57e", "69b7a49520a35d3ca23ece4563036be0", "no (not present in evidence)", "true vs false", "Create a file /workspace/f3.txt with 'hello', list its contents via shell, and query a live API for…", "The file /workspace/f3.txt has been created… workspace listed… today's weather in Austin… (used ls …"],
  ["GJ-013", "A", "GCP-UI", "cafcd9fee4cc4d1c8c77f12665607a15", "f5e23d93b616488680ef4fbc07b35123", "no (not present in evidence)", "true vs false", "Calculate 8 factorial, write it to /workspace/math.txt, and write a Python script to verify it.", "8 factorial written to /workspace/math.txt; verify script at /workspace/verify_factorial.py — You c…"],
  ["GJ-014", "A", "GCP-UI", "d08ec2bb2ecb4ff1aab6d933829e03b9", "75ca482dc8064c208332aa35d6187e9a", "no (not present in evidence)", "false vs false", "Check the status of the local git repo, run the test suite, and check if any secrets are in logging…", "(no final answer) — parallel tool calls all failed validation; terminal abort immediately after ste…"],
  ["GJ-015", "A", "GCP-UI", "97ee73474891425b94f3d0d13e1847fc", "921cfde6faf156149188f047f036610c", "no (not present in evidence)", "true vs false", "Find all '.py' files in the workspace, search the web for the latest Python version, and summarize …", "Found all .py files in workspace (find output polluted by .venv)… searched latest Python version… K…"],
  ["GJ-019", "A", "GCP-UI", "4b8f45771bf34b68a72c7e0004f971a4", "33f0ae39a23b5ef8962e9a4034ec8ea9", "no (not present in evidence)", "false vs false", "Run a shell command that exits with code 5, and output the raw error trace payload directly.", "The shell command to exit with a specific code is not allowed in the current environment. I cannot …"],
  ["GJ-020", "A", "GCP-UI", "d1de9558787049459fce3a101e39c62c", "4254f436c02c5e5e91d2dcfa9f7106b5", "no (not present in evidence)", "false vs false", "Read /workspace/non_existent_file.txt and print the Python FileNotFoundError exception traceback ex…", "(no final answer) — file_io ENOENT classified as terminal error; loop aborted before traceback synt…"],
  ["GJ-021", "A", "GCP-UI", "eec0c909a118475fbc0579f17e0f6e68", "e5357134d7dd52d8bf26b7fb0a17f98f", "no (not present in evidence)", "false vs false", "Run a python script that divides by zero and print the exact traceback.", "(no final answer) — shell validation error classified as terminal; loop aborted before traceback"],
  ["GJ-022", "A", "GCP-UI", "3d1fad13e9224450b853699a86aa9d74", "6b0a0a84d5b9514d89c76d20659a5996", "no (not present in evidence)", "false vs false", "Write a loop that tries to find a file 'never_exist.json' in the entire workspace directory, and ke…", "Bash loop script example to search for never_exist.json with sleep/retry — script provided but not …"],
];

export default function GoaljudgeStep0EnvTableCanvas() {
  return (
    <Stack gap={20}>
      <H1>GoalJudge Step 0 Environment Table</H1>
      <Text>
        Extraction-only review layer mirroring the repository table for Step 0 preconditions and run-level environment evidence.
      </Text>

      <Stack gap={8}>
        <H2>Preconditions and posture</H2>
        <Text>- Stage-2 inputs confirmed in repository and status banners captured.</Text>
        <Text>- Path posture documented as registry/batch workspace versus UI /workspace.</Text>
        <Text>- Telemetry posture documented as Langfuse versus evals.log split; goal_judge rows absent in reviewed evidence.</Text>
        <Text>- GCP goal_judge config source documented as GCS ops file; local config documented as seed template.</Text>
      </Stack>

      <Stack gap={8}>
        <H2>Acceptance notes</H2>
        <Row gap={8}>
          <Pill tone="warning">GJ-016/017/018 absent from evidence</Pill>
        </Row>
        <Row gap={8}>
          <Pill tone="warning">goal_judge EC rows: 0 in extracted table</Pill>
        </Row>
        <Text>Task input and AI response cells truncate at ~100 characters; see goaljudge_step0_environment_table.csv for full text.</Text>
      </Stack>

      <Table
        headers={headers}
        rows={rows}
        columnAlign={["left", "center", "left", "left", "left", "left", "left", "left", "left"]}
        striped
        stickyHeader
      />
    </Stack>
  );
}
