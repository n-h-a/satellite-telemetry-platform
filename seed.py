from sqlalchemy import select, func

from app.database import SessionLocal
from app.models import AlertRule

RULES = [
    # Electrical Power System — battery state of charge
    {'name': 'Low battery warning',             'metric': 'battery_soc_percent',    'operator': '<',  'threshold_value': 30.0,  'severity': 'WARNING',  'subsystem': 'Electrical Power System', 'enabled': True},
    {'name': 'Low battery critical',            'metric': 'battery_soc_percent',    'operator': '<',  'threshold_value': 20.0,  'severity': 'CRITICAL', 'subsystem': 'Electrical Power System', 'enabled': True},
    # Electrical Power System — battery voltage
    {'name': 'Battery undervoltage warning',    'metric': 'battery_voltage_v',      'operator': '<',  'threshold_value': 23.0,  'severity': 'WARNING',  'subsystem': 'Electrical Power System', 'enabled': True},
    {'name': 'Battery undervoltage critical',   'metric': 'battery_voltage_v',      'operator': '<',  'threshold_value': 21.0,  'severity': 'CRITICAL', 'subsystem': 'Electrical Power System', 'enabled': True},
    # Electrical Power System — bus voltage (split OR into separate rules)
    {'name': 'Bus voltage low warning',         'metric': 'bus_voltage_v',          'operator': '<',  'threshold_value': 26.0,  'severity': 'WARNING',  'subsystem': 'Electrical Power System', 'enabled': True},
    {'name': 'Bus voltage high warning',        'metric': 'bus_voltage_v',          'operator': '>',  'threshold_value': 30.0,  'severity': 'WARNING',  'subsystem': 'Electrical Power System', 'enabled': True},
    {'name': 'Bus voltage low critical',        'metric': 'bus_voltage_v',          'operator': '<',  'threshold_value': 24.0,  'severity': 'CRITICAL', 'subsystem': 'Electrical Power System', 'enabled': True},
    {'name': 'Bus voltage high critical',       'metric': 'bus_voltage_v',          'operator': '>',  'threshold_value': 32.0,  'severity': 'CRITICAL', 'subsystem': 'Electrical Power System', 'enabled': True},
    # Electrical Power System — power draw
    {'name': 'High power draw warning',         'metric': 'power_draw_w',           'operator': '>',  'threshold_value': 300.0, 'severity': 'WARNING',  'subsystem': 'Electrical Power System', 'enabled': True},
    {'name': 'High power draw critical',        'metric': 'power_draw_w',           'operator': '>',  'threshold_value': 400.0, 'severity': 'CRITICAL', 'subsystem': 'Electrical Power System', 'enabled': True},
    # Thermal — battery temperature (split OR into separate rules)
    {'name': 'Battery thermal low warning',     'metric': 'battery_temp_c',         'operator': '<',  'threshold_value': 0.0,   'severity': 'WARNING',  'subsystem': 'Thermal',                 'enabled': True},
    {'name': 'Battery thermal high warning',    'metric': 'battery_temp_c',         'operator': '>',  'threshold_value': 40.0,  'severity': 'WARNING',  'subsystem': 'Thermal',                 'enabled': True},
    {'name': 'Battery thermal low critical',    'metric': 'battery_temp_c',         'operator': '<',  'threshold_value': -10.0, 'severity': 'CRITICAL', 'subsystem': 'Thermal',                 'enabled': True},
    {'name': 'Battery thermal high critical',   'metric': 'battery_temp_c',         'operator': '>',  'threshold_value': 50.0,  'severity': 'CRITICAL', 'subsystem': 'Thermal',                 'enabled': True},
    # Command and Data Handling — OBC temperature
    {'name': 'OBC temperature warning',         'metric': 'obc_temp_c',             'operator': '>',  'threshold_value': 70.0,  'severity': 'WARNING',  'subsystem': 'Command and Data Handling', 'enabled': True},
    {'name': 'OBC temperature critical',        'metric': 'obc_temp_c',             'operator': '>',  'threshold_value': 85.0,  'severity': 'CRITICAL', 'subsystem': 'Command and Data Handling', 'enabled': True},
    # Command and Data Handling — storage
    {'name': 'Storage warning',                 'metric': 'storage_used_percent',   'operator': '>',  'threshold_value': 85.0,  'severity': 'WARNING',  'subsystem': 'Command and Data Handling', 'enabled': True},
    {'name': 'Storage critical',                'metric': 'storage_used_percent',   'operator': '>',  'threshold_value': 95.0,  'severity': 'CRITICAL', 'subsystem': 'Command and Data Handling', 'enabled': True},
    # Communications — RSSI
    {'name': 'Weak signal warning',             'metric': 'rssi_dbm',               'operator': '<',  'threshold_value': -105.0,'severity': 'WARNING',  'subsystem': 'Communications',          'enabled': True},
    {'name': 'Weak signal critical',            'metric': 'rssi_dbm',               'operator': '<',  'threshold_value': -115.0,'severity': 'CRITICAL', 'subsystem': 'Communications',          'enabled': True},
    # Communications — link margin
    {'name': 'Weak communications link',        'metric': 'link_margin_db',         'operator': '<',  'threshold_value': 3.0,   'severity': 'WARNING',  'subsystem': 'Communications',          'enabled': True},
    {'name': 'Critical communications link',    'metric': 'link_margin_db',         'operator': '<',  'threshold_value': 1.0,   'severity': 'CRITICAL', 'subsystem': 'Communications',          'enabled': True},
    # ADCS — attitude error
    {'name': 'Poor pointing warning',           'metric': 'attitude_error_deg',     'operator': '>',  'threshold_value': 5.0,   'severity': 'WARNING',  'subsystem': 'ADCS',                    'enabled': True},
    {'name': 'Poor pointing critical',          'metric': 'attitude_error_deg',     'operator': '>',  'threshold_value': 15.0,  'severity': 'CRITICAL', 'subsystem': 'ADCS',                    'enabled': True},
]

def seed():
    db = SessionLocal()
    try:
        if (db.scalar(select(func.count()).select_from(AlertRule)) or 0) > 0:
            print("Rules already seeded, skipping.")
            return
        
        db.add_all([AlertRule(**r) for r in RULES])
        db.commit()
        print(f"Seeded {len(RULES)} alert rules.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()

