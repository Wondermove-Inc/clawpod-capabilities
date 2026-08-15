import pathlib
import pytest

@pytest.fixture(autouse=True)
def isolated_display_metrics(monkeypatch):
    metrics = pathlib.Path(__file__).parent / "fixtures" / "xdpyinfo-static.sh"
    monkeypatch.setenv("DISPLAY", ":disposable-test")
    monkeypatch.setenv("DESKTOP_DISPOSABLE_DISPLAY", "1")
    monkeypatch.setenv("DESKTOP_METRICS_CLI", str(metrics))
