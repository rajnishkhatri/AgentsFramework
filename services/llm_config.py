"""ModelProfile registry and ChatLiteLLM factory (H2 pattern).

Provides LLM access via LiteLLM's LangChain-compatible wrapper.
This is the only file in services/ allowed to import from langchain.
"""

from __future__ import annotations

import logging
from typing import Any

from services.base_config import AgentConfig, ModelProfile

logger = logging.getLogger("services.llm_config")


class LLMService:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._profiles: dict[str, ModelProfile] = {m.name: m for m in config.models}

    def get_profile(self, name: str) -> ModelProfile:
        if name not in self._profiles:
            raise KeyError(f"Model profile '{name}' not found. Available: {list(self._profiles.keys())}")
        return self._profiles[name]

    def get_default_profile(self) -> ModelProfile:
        return self.get_profile(self._config.default_model)

    def get_llm(self, profile: ModelProfile) -> Any:
        """Returns a ChatLiteLLM instance for the given profile."""
        from langchain_litellm import ChatLiteLLM

        return ChatLiteLLM(
            model=profile.litellm_id,
            temperature=0,
            max_tokens=4096,
            streaming=True,
        )

    async def invoke(
        self,
        profile: ModelProfile,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        """Invoke LLM with the given profile and messages."""
        llm = self.get_llm(profile)
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        logger.info(
            "Invoking %s (%s tier)",
            profile.name,
            profile.tier,
            extra={"model": profile.name, "tier": profile.tier},
        )
        return await llm.ainvoke(lc_messages, **kwargs)

    async def invoke_with_tools(
        self,
        profile: ModelProfile,
        messages: list[Any],
        tool_schemas: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke LLM with LangChain messages and optional tool binding.

        Unlike ``invoke()``, this accepts pre-built LangChain message objects
        directly (including AIMessage with tool_calls and ToolMessage) so the
        full conversation history flows to the model.
        """
        llm = self.get_llm(profile)
        if tool_schemas:
            llm = llm.bind_tools(tool_schemas)

        logger.info(
            "Invoking %s (%s tier) with %d messages, %d tools",
            profile.name,
            profile.tier,
            len(messages),
            len(tool_schemas or []),
            extra={"model": profile.name, "tier": profile.tier},
        )
        return await llm.ainvoke(messages, **kwargs)
