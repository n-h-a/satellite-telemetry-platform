# Satellite Telemetry Metrics and Alert Thresholds

## Purpose

This document defines the first realistic metric set for the Satellite Telemetry Processing Platform.

These thresholds are not flight-certified limits. They are engineering-inspired defaults for a simulated small Earth observation satellite.

## Verification Summary

The metric categories are realistic. Spacecraft telemetry commonly supports ground teams in understanding spacecraft health, performance, status, and anomaly diagnosis. Verified sources support the following design choices:

1. Spacecraft telemetry is used to understand what a spacecraft is doing, diagnose anomalies, and support recovery.
2. Engineering and housekeeping telemetry are standard concepts.
3. Spacecraft subsystems commonly include electrical power, thermal, communications, attitude and orbit control, and data handling.
4. Ground systems need engineering telemetry to determine subsystem and payload status, health, and performance.
5. Onboard processor resource usage, such as CPU and memory, is a valid engineering telemetry concern.
6. Link margin is a real communications concept. NASA SmallSat guidance states that maintaining a 3 dB link margin is adequate for data return from a satellite in low Earth orbit at a slant range of 1,500 km.
7. Fault protection and safe mode concepts are realistic. JPL fault protection material describes safe mode as a lower-power, thermally safe state that preserves communications.

## Important Caveat About Thresholds

The exact warning and critical thresholds below are project defaults, not universal spacecraft limits. Real thresholds depend on the spacecraft bus, battery chemistry, orbit, thermal design, payload, communications link budget, operational modes, and mission rules.

For this project, thresholds should be stored as configurable data in an `alert_rules` table rather than hardcoded permanently in application code.

## Metric Set

| Metric | Subsystem | Unit | Normal Range | Warning | Critical | Why It Matters |
|---|---|---:|---:|---:|---:|---|
| `battery_voltage_v` | Electrical Power System | V | 24 to 32 | `< 23` | `< 21` | Low battery voltage can threaten spacecraft survival. |
| `battery_soc_percent` | Electrical Power System | % | 40 to 100 | `< 30` | `< 20` | Simple operational indicator for remaining energy. |
| `battery_temp_c` | Thermal and EPS | C | 5 to 35 | `< 0` or `> 40` | `< -10` or `> 50` | Batteries are temperature sensitive. |
| `bus_voltage_v` | Electrical Power System | V | 27 to 29 | `< 26` or `> 30` | `< 24` or `> 32` | Main spacecraft power bus stability. |
| `solar_array_current_a` | Electrical Power System | A | 0 to 12 | `< 1 while sunlit` | `0 while sunlit` | Detects poor solar generation during sunlit periods. |
| `power_draw_w` | Electrical Power System | W | 80 to 250 | `> 300` | `> 400` | Detects excessive load or incorrect operating mode. |
| `obc_temp_c` | Command and Data Handling | C | -10 to 60 | `> 70` | `> 85` | Onboard computer overheating risk. |
| `obc_cpu_percent` | Command and Data Handling | % | 5 to 70 | `> 85 for 5 min` | `> 95 for 10 min` | Detects software overload or runaway process. |
| `storage_used_percent` | Command and Data Handling | % | 0 to 80 | `> 85` | `> 95` | Storage exhaustion can block payload data collection. |
| `rssi_dbm` | Communications | dBm | -95 to -60 | `< -105` | `< -115` | Weak received signal strength. |
| `link_margin_db` | Communications | dB | 3 to 20 | `< 3` | `< 1` | Low margin means communications are at risk. |
| `attitude_error_deg` | ADCS | deg | 0 to 2 | `> 5` | `> 15` | Poor pointing can affect imaging, power generation, and communications. |

## Additional Metrics for Later Versions

### Electrical Power System

| Metric | Unit | Normal Range | Warning | Critical | Notes |
|---|---:|---:|---:|---:|---|
| `battery_current_a` | A | -5 to 8 | `< -8` or `> 10` | `< -12` or `> 15` | Negative can represent discharging, positive can represent charging depending on convention. |
| `eps_mode` | enum | nominal | safe, eclipse, power_save | fault | Useful for contextual alerting. |
| `solar_array_voltage_v` | V | mission-defined | outside expected range | severe deviation | Useful with current to estimate generated power. |

### Thermal

| Metric | Unit | Normal Range | Warning | Critical | Notes |
|---|---:|---:|---:|---:|---|
| `payload_temp_c` | C | -10 to 45 | `< -20` or `> 55` | `< -30` or `> 65` | Protects Earth observation payload. |
| `radio_temp_c` | C | -10 to 55 | `> 65` | `> 75` | Radio overheating can affect communications. |
| `reaction_wheel_temp_c` | C | -10 to 60 | `> 70` | `> 85` | ADCS actuator health. |

### Communications

| Metric | Unit | Normal Range | Warning | Critical | Notes |
|---|---:|---:|---:|---:|---|
| `snr_db` | dB | 10 to 30 | `< 6` | `< 3` | Signal quality. |
| `packet_loss_percent` | % | 0 to 2 | `> 5` | `> 15` | Data reliability. |
| `downlink_rate_kbps` | kbps | 64 to 2048 | `< 32 during contact` | `0 during contact` | Underperforming contact window. |
| `last_contact_age_min` | min | 0 to 90 | `> 120` | `> 240` | Detects missed ground contact. |

### Attitude Determination and Control System, ADCS

| Metric | Unit | Normal Range | Warning | Critical | Notes |
|---|---:|---:|---:|---:|---|
| `body_rate_deg_s` | deg/s | 0 to 0.5 | `> 2` | `> 5` | Possible tumble or poor control. |
| `reaction_wheel_speed_rpm` | rpm | -4000 to 4000 | `abs > 5000` | `abs > 6500` | Wheel saturation risk. |
| `magnetometer_norm_ut` | uT | 20 to 70 | outside expected range | severe spike or dropout | Sensor anomaly. |
| `sun_sensor_valid` | boolean | true while sunlit | false while sunlit | repeated false while sunlit | Attitude sensor issue. |

### Command and Data Handling

| Metric | Unit | Normal Range | Warning | Critical | Notes |
|---|---:|---:|---:|---:|---|
| `obc_memory_percent` | % | 20 to 75 | `> 85` | `> 95` | Memory leak or overload. |
| `reboot_count_24h` | count | 0 | `>= 1` | `>= 3` | Possible software fault or radiation event. |
| `uptime_seconds` | seconds | increasing | sudden reset | repeated resets | Reset detection. |
| `command_queue_depth` | count | 0 to 20 | `> 50` | `> 100` | Commands are backing up. |

### Payload Health

For the first fictional mission, use an Earth observation satellite.

| Metric | Unit | Normal Range | Warning | Critical | Notes |
|---|---:|---:|---:|---:|---|
| `payload_mode` | enum | idle, imaging, downlink | unexpected mode | stuck mode | Operational state. |
| `image_capture_rate` | images/min | mission-defined | below expected | zero during imaging pass | Payload productivity. |
| `data_backlog_mb` | MB | 0 to 5000 | `> 7000` | `> 9000` | Need downlink soon. |
| `payload_error_count` | count/hr | 0 | `> 5` | `> 20` | Instrument fault. |

## Alert Severity Model

Use three severities.

| Severity | Meaning | Example |
|---|---|---|
| `INFO` | Interesting, not urgent | Satellite entered eclipse mode. |
| `WARNING` | Needs attention | Battery state of charge is below 30%. |
| `CRITICAL` | Could threaten mission, spacecraft health, or data return | Battery state of charge is below 20%. |

## Recommended Rule Types

Do not limit the alert system to simple thresholds. Implement three rule types.

### 1. Threshold Rule

A single reading crosses a configured limit.

```text
battery_soc_percent < 20
```

### 2. Rolling Window Rule

A condition remains true over a time window.

```text
obc_cpu_percent > 90 for 10 minutes
```

### 3. Correlation Rule

Two or more metrics together indicate a likely fault.

```text
attitude_error_deg > 10 AND link_margin_db < 3
```

## Starting Rules

| Rule Name | Expression | Severity | Subsystem |
|---|---|---|---|
| Low battery warning | `battery_soc_percent < 30` | WARNING | EPS |
| Low battery critical | `battery_soc_percent < 20` | CRITICAL | EPS |
| Battery undervoltage warning | `battery_voltage_v < 23` | WARNING | EPS |
| Battery undervoltage critical | `battery_voltage_v < 21` | CRITICAL | EPS |
| Battery thermal warning | `battery_temp_c < 0 OR battery_temp_c > 40` | WARNING | Thermal |
| Battery thermal critical | `battery_temp_c < -10 OR battery_temp_c > 50` | CRITICAL | Thermal |
| Weak communications link | `link_margin_db < 3` | WARNING | Communications |
| Critical communications link | `link_margin_db < 1` | CRITICAL | Communications |
| Poor pointing warning | `attitude_error_deg > 5` | WARNING | ADCS |
| Poor pointing critical | `attitude_error_deg > 15` | CRITICAL | ADCS |
| Storage warning | `storage_used_percent > 85` | WARNING | C&DH |
| Storage critical | `storage_used_percent > 95` | CRITICAL | C&DH |
| Sustained CPU warning | `obc_cpu_percent > 85 for 5 minutes` | WARNING | C&DH |
| Sustained CPU critical | `obc_cpu_percent > 95 for 10 minutes` | CRITICAL | C&DH |
| Missed contact warning | `last_contact_age_min > 120` | WARNING | Communications |
| Missed contact critical | `last_contact_age_min > 240` | CRITICAL | Communications |
| Possible antenna pointing issue | `attitude_error_deg > 10 AND link_margin_db < 3` | CRITICAL | ADCS and Communications |

## Backend Design Implications

### Where Detection Happens

For the first version, it is acceptable to check thresholds inline inside `POST /telemetry`. Later, move this logic into a worker when queues are added.

### Data Model Suggestions


#### `alert_rules`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key. |
| `metric` | text | Metric to evaluate. |
| `operator` | text | `<`, `>`, `<=`, `>=`, `==`. |
| `threshold_value` | numeric | Value used by threshold rules. |
| `duration_seconds` | integer | Optional, used for rolling window rules. |
| `severity` | text | `INFO`, `WARNING`, `CRITICAL`. |
| `subsystem` | text | EPS, Thermal, Communications, ADCS, C&DH, Payload. |
| `enabled` | boolean | Allows rules to be disabled. |

#### `alerts`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key. |
| `satellite_id` | UUID | References satellite. |
| `rule_id` | UUID | References alert rule. |
| `metric` | text | Triggering metric. |
| `observed_value` | numeric | Value that triggered alert. |
| `severity` | text | `INFO`, `WARNING`, `CRITICAL`. |
| `message` | text | Human-readable alert. |
| `triggered_at` | timestamptz | Alert creation time. |
| `resolved_at` | timestamptz | Optional. |

## Suggested API Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /telemetry` | Ingest telemetry from satellite simulator. |
| `GET /telemetry/recent` | Return recent stored telemetry from PostgreSQL or Redis cache. |
| `GET /satellites` | List satellites. |
| `GET /alerts` | Return alert history. |
| `POST /alert-rules` | Create alert rule, optional later. |
| `GET /health` | Health check for API, database, and Redis. |

## README Framing

Use this project description in the repository README.

> This project simulates a mission-control-style telemetry platform for a small Earth observation satellite. It ingests spacecraft state-of-health telemetry, stores raw readings, evaluates configurable alert rules across power, thermal, communications, onboard computing, and attitude-control subsystems, and exposes APIs for recent telemetry and alert history.

## Sources Used For Verification

1. JPL, `Flight Software Case Study: Spacecraft Telemetry`, 2024. Supports the importance of telemetry for visibility, anomaly diagnosis, and the categories of Event Reporting, Engineering, Housekeeping, and Accountability, and data products. https://www-robotics.jpl.nasa.gov/media/documents/Flight_Software_Case_Study_Spacecraft_Telemetry.pdf
2. ECSS, `Space engineering, Space segment operability`, ECSS-E-ST-70-11C Rev.1 DIR1, 2024. Supports engineering telemetry for spacecraft health, subsystem and payload performance, housekeeping telemetry, onboard monitoring, and CPU and memory usage telemetry. https://ecss.nl/wp-content/uploads/2024/07/ECSS-E-ST-70-11C-Rev.1-DIR1%285July2024%29.pdf
3. ESA, `Virtual Spacecraft, Enhanced Monitoring and Diagnostics through Virtual Reality`. Supports typical spacecraft subsystem categories: attitude and orbit control, electrical power, thermal, communications, and data handling. https://www.esa.int/Enabling_Support/Operations/Virtual_Spacecraft_br_Enhanced_Monitoring_Diagnostics_through_Virtual_Reality
4. NASA Small Spacecraft Systems Virtual Institute, `Ground Data Systems and Mission Operations`. Supports link budget and link margin concepts, including 3 dB link margin for a LEO example. https://www.nasa.gov/smallsat-institute/sst-soa/ground-data-systems-and-mission-operations/
5. JPL, `Fault Protection Techniques in JPL Spacecraft`. Supports safe mode and fault response concepts, including lower power state, thermally safe attitude, and communications preservation. https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/05-2750.pdf
