from starter_service.config import load_config


def test_false_zero_and_empty_values_are_not_missing():
    assert load_config({"enabled": True}, {}, {}, {"enabled": False})["enabled"] is False
    assert load_config({"workers": 4}, {}, {"WORKERS": 0}, {})["workers"] == 0
    assert load_config({"label": "default"}, {"label": ""}, {}, {})["label"] == ""


def test_command_line_environment_file_default_order():
    assert load_config(
        {"a": 1, "b": 2, "c": 3, "d": 4},
        {"b": 20, "c": 30, "d": 40},
        {"C": 300, "D": 400},
        {"d": 4000},
    ) == {"a": 1, "b": 20, "c": 300, "d": 4000}
