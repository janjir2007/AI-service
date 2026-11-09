"""Deterministic engineering calculations — LLM must not perform these."""


def calculate_area(length: float, width: float) -> float:
    return length * width


def calculate_volume(length: float, width: float, thickness: float) -> float:
    return length * width * thickness


def calculate_weight(volume: float, density: float) -> float:
    return volume * density


def calculate_material_quantity(
    base_quantity: float,
    consumption_rate: float,
    waste_factor: float = 0.0,
) -> float:
    return base_quantity * consumption_rate * (1.0 + waste_factor)
