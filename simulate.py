import os
import random
import time

import requests

BASE_URL = os.getenv("SIMULATOR_BASE_URL", "http://localhost:8000")

METRICS = {
    "battery_voltage_v":    ("V",   24.0,  32.0,  20.0,  34.0),
    "battery_soc_percent":  ("%",   40.0, 100.0,  15.0, 105.0),
    "battery_temp_c":       ("C",    5.0,  35.0, -15.0,  55.0),
    "bus_voltage_v":        ("V",   27.0,  29.0,  23.0,  33.0),
    "solar_array_current_a":("A",    1.0,  12.0,   0.0,  13.0),
    "power_draw_w":         ("W",   80.0, 250.0,  60.0, 420.0),
    "obc_temp_c":           ("C",  -10.0,  60.0, -15.0,  90.0),
    "obc_cpu_percent":      ("%",    5.0,  70.0,   0.0,  99.0),
    "storage_used_percent": ("%",    0.0,  80.0,   0.0,  99.0),
    "rssi_dbm":             ("dBm", -95.0, -60.0, -120.0, -55.0),
    "link_margin_db":       ("dB",   3.0,  20.0,  -2.0,  22.0),
    "attitude_error_deg":   ("deg",  0.0,   2.0,   0.0,  20.0),
}

SOURCE_IDS = ["SAT-1", "SAT-2", "SAT-3", "SAT-4", "SAT-5"]

ANOMALY_RATE = 0.1


def sample_value(metric: str) -> float:
    unit, lo, hi, anomaly_lo, anomaly_hi = METRICS[metric]
    if random.random() < ANOMALY_RATE:
        return round(random.uniform(anomaly_lo, anomaly_hi), 4)
    return round(random.uniform(lo, hi), 4)


def send_reading(source_id: str, metric: str) -> None:
    unit = METRICS[metric][0]
    payload = {
        "source_id": source_id,
        "metric": metric,
        "value": sample_value(metric),
        "unit": unit
    }

    try:
        r = requests.post(f"{BASE_URL}/telemetry", json=payload, timeout=5)
        r.raise_for_status()
        print(f"{source_id} {metric:<25} {payload['value']:>10} {unit}")
    except requests.RequestException as e:
        print(f"[error] {e}")


if __name__ == "__main__":
    print(f"Sending telemetry to {BASE_URL} - Ctrl+C to stop\n")
    while True:
        send_reading(
            source_id=random.choice(SOURCE_IDS),
            metric=random.choice(list(METRICS))
        )
        time.sleep(random.uniform(1.0, 5.0))
