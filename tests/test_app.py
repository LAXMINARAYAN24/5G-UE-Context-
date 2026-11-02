from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_default_run_and_scenario_switch():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=30)
    assert not app.exception
    assert app.metric[0].value == "100%"
    assert len(app.metric) == 8
    assert not app.warning

    app.sidebar.selectbox[0].select("idle_resume")
    app.run(timeout=30)
    assert not app.exception
    assert app.warning

    app.sidebar.button[0].click().run(timeout=30)
    assert not app.exception
    assert not app.warning
    assert app.metric[1].value == "N/A"


def test_dashboard_renders_benchmark_and_session_explorer():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=30)
    assert not app.exception
    assert any("Checked-in benchmark comparison" in element.value for element in app.subheader)
    assert any("Filtered event timeline" in element.value for element in app.subheader)
    assert app.dataframe

    app.multiselect(key="event_filter").set_value(["procedure_begin"]).run(timeout=30)
    assert not app.exception
    timeline = next(frame.value for frame in app.dataframe if "event" in frame.value.columns)
    assert set(timeline["event"]) == {"procedure_begin"}
