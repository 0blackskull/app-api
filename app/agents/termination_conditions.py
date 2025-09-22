from typing import Sequence, Optional
from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.messages import StopMessage

class MessageTermination(TerminationCondition):
    """Terminates the conversation when a specified agent outputs a message ending with a specified keyword (e.g., 'APPROVE' for VerificationAgent)."""

    def __init__(self, extra_terminations=None):
        super().__init__()
        self._terminated = False
        # extra_terminations: list of (agent_name, keyword) pairs
        self.extra_terminations = extra_terminations or []

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(self, messages: Sequence["ChatMessage"]) -> Optional[StopMessage]:
        if self._terminated:
            return StopMessage(
                content="Termination condition already met.",
                source="MessageTermination",
            )

        for message in messages:
            if (
                hasattr(message, "content")
                and hasattr(message, "source")
                and isinstance(message.content, str)
            ):
                content = message.content.strip()
                # Only check extra terminations
                for agent, keyword in self.extra_terminations:
                    if getattr(message, "source", None) == agent and content.endswith(keyword):
                        self._terminated = True
                        return StopMessage(
                            content=f"Received '{keyword}' message from {agent}.",
                            source="MessageTermination",
                        )
        return None

    async def reset(self) -> None:
        self._terminated = False 