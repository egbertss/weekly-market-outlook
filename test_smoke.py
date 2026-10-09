import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_demo_run(tmp_path):
    subprocess.run(
        [sys.executable, "outlook.py", "--demo", "--out", str(tmp_path)],
        cwd=ROOT, check=True,
    )
    files = list(tmp_path.glob("weekly_outlook_*_DEMO.html"))
    assert len(files) == 1
    html = files[0].read_text(encoding="utf-8")
    assert "DEMO DATA" in html
    assert html.count("data:image/png;base64") >= 4
