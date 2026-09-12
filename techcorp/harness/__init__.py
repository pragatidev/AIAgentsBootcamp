"""TechCorp coding-agent harness: map file, permissions, sandboxed loop."""

from techcorp.harness.coding_agent import (
    AGENTS_PATH,
    PERMISSIONS,
    build_coding_desk,
    check_permission,
    load_agents_md,
    make_tools,
    planted_shell_table,
)
from techcorp.harness.sandboxed_loop import (
    SANDBOX,
    STOPPED,
    run_loop,
    write_under_root,
)

__all__ = [
    "AGENTS_PATH",
    "PERMISSIONS",
    "SANDBOX",
    "STOPPED",
    "build_coding_desk",
    "check_permission",
    "load_agents_md",
    "make_tools",
    "planted_shell_table",
    "run_loop",
    "write_under_root",
]
