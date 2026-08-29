from lumaguard.main_window import MainWindow
from lumaguard.constants import COOLDOWN_OPTIONS, PAUSE_WINDOW_OPTIONS


def test_cooldown_duration_labels():
    assert MainWindow._format_duration(1) == "1 minute"
    assert MainWindow._format_duration(45) == "45 minutes"
    assert MainWindow._format_duration(90) == "1 hour 30 minutes"
    assert MainWindow._format_duration(1440) == "1 day"


def test_cooldown_options_cover_short_and_long_delays():
    values = [minutes for _, minutes in COOLDOWN_OPTIONS]
    assert values == sorted(values)
    assert {1, 2, 3, 10, 20, 45, 90, 240, 720, 1440}.issubset(values)


def test_pause_window_options_include_close_bound_and_bounded_choices():
    values = [minutes for _, minutes in PAUSE_WINDOW_OPTIONS]
    assert values == sorted(values)
    assert values[0] == 0
    assert 30 in values
    assert values[-1] == 120
