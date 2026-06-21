"""Allow running as: python -m cc_tmux_bridge <command>"""
import sys
from .cli import main
sys.exit(main())
