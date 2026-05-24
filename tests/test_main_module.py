import subprocess
import sys
from pathlib import Path


def test_python_m_contx_version_runs():
    result = subprocess.run(
        [sys.executable, "-m", "contx", "version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout
