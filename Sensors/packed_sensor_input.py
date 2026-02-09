def get_packed_sensor_input() -> tuple[float, ...]:
    """Get packed sensor input from all sensors."""
    # temp,humidity,soil humidity
    data = "23,70,50"
    data = map(float, data.split(","))
    return tuple(data)