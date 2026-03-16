"""
Base agent class with shared session management and chat logic.
Subclasses provide name, tools, and system prompt.
"""

import asyncio
import os
from typing import Optional, List
from strands import Agent
from strands.session import FileSessionManager


class BaseAgent:
    """Base class for Strands-based agents with multi-turn conversation."""

    name: str = "BaseAgent"
    default_model: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def __init__(self, session_id: str, model_id: Optional[str] = None):
        self.session_id = session_id
        self.model_id = model_id or self.default_model

        self.session_manager = FileSessionManager(
            session_id=session_id,
            storage_dir=os.path.join(os.path.dirname(__file__), ".sessions"),
        )

        self.agent = Agent(
            name=self.name,
            model=self.model_id,
            session_manager=self.session_manager,
            system_prompt=self._get_instructions(),
            tools=self._get_tools(),
        )

    def _get_tools(self) -> List:
        raise NotImplementedError

    def _get_instructions(self) -> str:
        raise NotImplementedError

    def chat(self, message: str) -> str:
        async def _chat():
            response = await self.agent.invoke_async(message)
            return self._extract_text(response)
        return asyncio.run(_chat())

    @staticmethod
    def _extract_text(response) -> str:
        if hasattr(response, "text"):
            return response.text
        if hasattr(response, "content"):
            if isinstance(response.content, list):
                parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        parts.append(block["text"])
                    elif isinstance(block, str):
                        parts.append(block)
                if parts:
                    return "\n".join(parts)
            return str(response.content)
        return str(response)

    def close(self):
        pass
