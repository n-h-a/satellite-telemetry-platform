import http from 'k6/http';
import { check } from 'k6';

const METRICS = ["battery_voltage_v", "obc_cpu_percent", "rssi_dbm", "link_margin_db"];
const SOURCES = ["SAT-1", "SAT-2", "SAT-3", "SAT-4", "SAT-5"];

export const options = {
    stages: [
        { duration: '15s', target: 10 },   // ramp up
        { duration: '30s', target: 10 },   // sustain
        { duration: '10s', target: 0 },    // ramp down
    ],
};

export default function () {
    const payload = JSON.stringify({
        source_id: SOURCES[Math.floor(Math.random() * SOURCES.length)],
        metric: METRICS[Math.floor(Math.random() * METRICS.length)],
        value: Math.random() * 100,
        unit: "unit",
    });

    const res = http.post('http://localhost:8000/telemetry', payload, {
        headers: { 'Content-Type': 'application/json' },
    });

    check(res, { 'status is 201': (r) => r.status === 201 });
}