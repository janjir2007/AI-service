import pytest

from app.tools.calculator import (
    calculate_area,
    calculate_material_quantity,
    calculate_volume,
    calculate_weight,
)


def test_calculate_volume():
    assert calculate_volume(10000, 7, 0.05) == 3500.0


def test_calculate_area():
    assert calculate_area(10, 5) == 50


def test_calculate_weight():
    assert calculate_weight(2, 800) == 1600


def test_calculate_material_quantity_waste():
    assert calculate_material_quantity(100, 1.02, 0.05) == pytest.approx(107.1)
