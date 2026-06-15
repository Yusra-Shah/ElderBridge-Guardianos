"""
Pytest configuration — ensures the backend/ directory is on sys.path so that
`import orchestrator`, `import schemas`, `import agents` all resolve when
running `pytest` from any working directory.
"""
import os
import sys

# Insert backend/ at the front of the path so all module imports use the
# local source tree rather than any installed package.
sys.path.insert(0, os.path.dirname(__file__))
