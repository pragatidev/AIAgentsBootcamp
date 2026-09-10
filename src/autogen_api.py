"""Teaching stand-in for `from autogen import AssistantAgent, UserProxyAgent`.

The 2025 AutoGen import is gone. AG2 1.0 is a different API. These two classes
keep the live lecture shape and talk through get_llm() from .env.
"""

from __future__ import annotations

from src.llm import get_llm


class AssistantAgent:
    def __init__(self, name: str, llm_config=None, system_message: str | None = None) -> None:
        self.name = name
        self.llm_config = llm_config
        self.system_message = system_message or "You are a helpful business assistant. Be brief."
        self.llm = get_llm()

    def reply(self, text: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = self.llm.invoke(
            [
                SystemMessage(content=self.system_message),
                HumanMessage(content=text),
            ]
        )
        content = getattr(out, "content", str(out))
        if isinstance(content, list):
            content = "".join(
                (b.get("text") if isinstance(b, dict) else str(b)) for b in content
            )
        return str(content)


class UserProxyAgent:
    def __init__(
        self,
        name: str,
        human_input_mode: str = "NEVER",
        max_consecutive_auto_reply: int = 1,
        code_execution_config=None,
        **kwargs,
    ) -> None:
        self.name = name
        self.human_input_mode = human_input_mode
        self.max_consecutive_auto_reply = max_consecutive_auto_reply
        self.code_execution_config = code_execution_config

    def initiate_chat(self, recipient: AssistantAgent, message: str = "", **kwargs):
        print(f"{self.name} (to {recipient.name}):\n")
        print(message)
        print()
        print("-" * 80)
        reply = recipient.reply(message)
        print(f"{recipient.name} (to {self.name}):\n")
        print(reply)
        print()
        return reply


class GroupChat:
    def __init__(self, agents, messages=None, max_round: int = 4, **kwargs) -> None:
        self.agents = agents
        self.messages = messages or []
        self.max_round = max_round


class GroupChatManager:
    def __init__(self, groupchat: GroupChat, llm_config=None) -> None:
        self.groupchat = groupchat
        self.llm_config = llm_config

    def run(self, message: str) -> str:
        text = message
        for agent in self.groupchat.agents:
            if hasattr(agent, "reply"):
                text = agent.reply(text)
        return text
