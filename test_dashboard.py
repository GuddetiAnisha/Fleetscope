from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_dashboard_loads_and_scenario():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    assert not app.exception
    assert not app.error
    app.slider(key='weight_registry').set_value(0.0).run(timeout=60)
    assert not app.exception and not app.error
