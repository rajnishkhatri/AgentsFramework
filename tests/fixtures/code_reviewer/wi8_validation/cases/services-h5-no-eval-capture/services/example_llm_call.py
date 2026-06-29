"""Service that calls the LLM but skips eval_capture.record — violates H5."""

from services.base_config import AgentConfig
from services.llm_config import LLMService


async def call_model(prompt: str) -> str:
    """Invoke the LLM and return the answer text.

    BUG (H5): every LLM call must be recorded via eval_capture.record with
    user_id + task_id; this call site records nothing, so the run is invisible
    to the eval/governance pipeline.
    """
    config = AgentConfig(default_model="gpt-4o-mini", models=[])
    llm = LLMService(config)
    response = await llm.invoke(None, [{"role": "user", "content": prompt}])
    return getattr(response, "content", str(response))
