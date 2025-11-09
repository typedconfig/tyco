import json
import subprocess
import sys
from pathlib import Path


def run_cli(tmp_path, content):
    path = tmp_path / "config.tyco"
    path.write_text(content)
    result = subprocess.run(
        [sys.executable, "-m", "tyco", str(path), "--format", "json", "--pretty"],
        capture_output=True,
        text=True,
    )
    return result


def test_cli_success(tmp_path):
    result = run_cli(
        tmp_path,
        """
str env: production

Service:
 *str name:
  int port:
  - api, 3000
""",
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["env"] == "production"
    assert output["Service"][0]["port"] == 3000


def test_cli_reports_parse_errors(tmp_path):
    path = tmp_path / "broken.tyco"
    path.write_text("str env production")  # missing colon
    result = subprocess.run(
        [sys.executable, "-m", "tyco", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "broken.tyco" in result.stderr
    assert "env" in result.stderr
