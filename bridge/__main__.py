"""Allow running as: python -m bridge <command>"""
import sys
from .cli import main
sys.exit(main())
