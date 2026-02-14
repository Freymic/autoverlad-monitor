import pytest
from datetime import datetime, timedelta
# Angenommen, deine Funktionen sind importierbar
from autoverlad_app import get_trend_arrow, calculate_minutes

def test_calculate_minutes_hours_and_mins():
    # Testet, ob "1 Stunde 20 Minuten" korrekt zu 80 min wird
    input_text = "Wartezeit Oberwald: 1 Stunde 20 Minuten"
    assert calculate_minutes(input_text) == 80

def test_trend_logic_increase():
    # Testet, ob der Pfeil nach oben geht, wenn die Zeit steigt
    assert get_trend_arrow(current=30, old=10) == "⬆️"

def test_trend_logic_decrease():
    assert get_trend_arrow(current=5, old=20) == "⬇️"
