from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


@pytest.mark.parametrize("language", ["C++", "Python", "Java"])
def test_dashboard_analyzes_each_language(language):
    app = AppTest.from_file(str(APP_PATH), default_timeout=20).run()
    app.get_by_key("selected_language").set_value(language)
    app.form_submit_button[0].click().run(timeout=20)

    assert not app.exception
    assert not app.error

    result = app.session_state["analysis_result"]
    assert result["language"] == language
    assert result["complexity"]["complexity"] >= 1
    assert result["paths"]
