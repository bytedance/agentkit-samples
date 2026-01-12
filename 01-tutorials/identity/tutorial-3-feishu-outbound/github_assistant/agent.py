# Agent definition for ADK web discovery
import sys
from pathlib import Path

# Add parent directory to path to import main module
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from main import root_agent, agent

__all__ = ["root_agent", "agent"]
