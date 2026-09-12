"""Research agent. Pytest stays green with no live model."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from deepagents.backends import FilesystemBackend

from research_agent.agent import DEFAULT_SUBAGENTS, build_research_agent, files_from_state
from research_agent.tools import read_document
from tests.fixtures.fake_model import FakeChatModel, ScriptedToolChatModel


def _tool_call(name: str, args: dict, call_id: str) -> dict:
    return {
        "name": name,
        "args": args,
        "id": call_id,
        "type": "tool_call",
    }


def test_subagent_declared():
    assert len(DEFAULT_SUBAGENTS) == 1
    reader = DEFAULT_SUBAGENTS[0]
    assert reader["name"] == "reader"
    assert "return-complaint" in reader["description"]
    tools = reader["tools"]
    names = [getattr(item, "name", None) or getattr(item, "__name__", "") for item in tools]
    assert "read_document" in names
    assert read_document in tools


def test_plan_written():
    model = FakeChatModel(
        tool_script=[
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call(
                        "write_todos",
                        {
                            "todos": [
                                {
                                    "content": "List return documents",
                                    "status": "in_progress",
                                },
                                {
                                    "content": "Draft the report",
                                    "status": "pending",
                                },
                            ]
                        },
                        "call_todos_1",
                    )
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call(
                        "write_file",
                        {
                            "file_path": "/notes.md",
                            "content": "fixture notes",
                        },
                        "call_write_notes",
                    )
                ],
            ),
            AIMessage(content="Plan is in todos. Notes are in /notes.md."),
        ]
    )
    assert isinstance(model, ScriptedToolChatModel)
    agent = build_research_agent(model=model)
    out = agent.invoke(
        {"messages": [{"role": "user", "content": "research returns"}]}
    )
    todos = out.get("todos") or []
    assert len(todos) == 2
    assert todos[0]["content"] == "List return documents"
    assert todos[1]["content"] == "Draft the report"


def test_report_file_written():
    model = FakeChatModel(
        tool_script=[
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call(
                        "write_file",
                        {
                            "file_path": "/reports/return_complaints.md",
                            "content": (
                                "Fixture report\n\n"
                                "Sources\n"
                                "- data/tickets.jsonl\n"
                            ),
                        },
                        "call_write_report",
                    )
                ],
            ),
            AIMessage(content="Wrote /reports/return_complaints.md"),
        ]
    )
    agent = build_research_agent(model=model)
    out = agent.invoke(
        {"messages": [{"role": "user", "content": "write the report"}]}
    )
    files = files_from_state(out)
    key = None
    for candidate in files:
        name = str(candidate).replace("\\", "/")
        if name.rstrip("/").endswith("reports/return_complaints.md"):
            key = candidate
            break
    assert key is not None, sorted(files.keys())
    data = files[key]
    text = data.get("content") if isinstance(data, dict) else str(data)
    assert "Fixture report" in text
    assert "Sources" in text


def test_real_backend_writes_to_disk(tmp_path):
    model = FakeChatModel(
        tool_script=[
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call(
                        "write_file",
                        {
                            "file_path": "/reports/return_complaints.md",
                            "content": "disk fixture report\n",
                        },
                        "call_write_disk",
                    )
                ],
            ),
            AIMessage(content="Wrote /reports/return_complaints.md"),
        ]
    )
    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=True)
    agent = build_research_agent(model=model, backend=backend)
    agent.invoke({"messages": [{"role": "user", "content": "write the report"}]})
    path = tmp_path / "reports" / "return_complaints.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "disk fixture report" in text
