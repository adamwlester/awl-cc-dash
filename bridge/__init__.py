"""
CC tmux Bridge — Programmatic control of Claude Code TUI sessions in WSL2/tmux.
"""

from .bridge import TmuxBridge, parse_permission_prompt

__all__ = ["TmuxBridge", "parse_permission_prompt"]
__version__ = "0.1.0"
