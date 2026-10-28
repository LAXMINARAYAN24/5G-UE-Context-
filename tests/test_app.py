from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_default_run_and_scenario_switch():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=30)
    assert not app.exception
    assert app.metric[0].value == "1"
    app.sidebar.selectbox[0].select("idle_resume")
    app.sidebar.button[0].click().run(timeout=30)
    assert not app.exception
    assert app.metric[1].value == "N/A"
