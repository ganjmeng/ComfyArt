"""One command: python tests/agent_regression/run.py  -> runs the set and prints report/summary.md."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
env = {**os.environ, "COMFYART_SKIP_NODE_TESTS": os.environ.get("COMFYART_SKIP_NODE_TESTS", "1"),
       "AGENT_REGRESSION_OUT": os.environ.get("AGENT_REGRESSION_OUT") or str(HERE / "report")}
code = subprocess.call([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE), *sys.argv[1:]],
                       cwd=HERE.parents[1], env=env)
out = Path(env.get("AGENT_REGRESSION_OUT") or HERE / "report") / "summary.md"
if out.exists():
    print(out.read_text())
sys.exit(code)
