from app.db import init_db, upsert_product, upsert_connector, list_products
from app.services.catalog_ai import build_product, relation_edges, product_hash
from app.services.enterprise_ai import family_and_relationships, anomaly_findings, publish_gate

def add(sku, manufacturer, mpn, sources):
    existing = list_products()
    p = build_product(sku, manufacturer, mpn, sources)
    rel = family_and_relationships(p, existing)
    p["family"] = rel["family_key"]
    p["anomalies"] = anomaly_findings(p)
    p["publish_gate"] = publish_gate(p)
    p["record_hash"] = product_hash(p)
    p["_source_documents"] = sources
    upsert_product(p, relation_edges(p) + rel["relationships"])

init_db()

# 1. Schneider Contactor (with conflict for demo)
add(
    "UGI-CONTACTOR-001",
    "Schneider Electric",
    "LC1D18M7-DEMO",
    [
        {"name": "Schneider Primary Technical Datasheet", "type": "manufacturer_datasheet", "text": "Schneider Electric LC1D18M7 TeSys D contactor. Poles: 3. Current rating: 18 A. Coil voltage: 220 VAC 50/60 Hz. Mounting type: DIN rail. Operating temperature: -5 to 60 C. IP Rating: IP20. UL, CE, RoHS certified."},
        {"name": "Distributor FastSupply Listing", "type": "authorized_distributor", "text": "Schneider LC1D18M7 3-pole contactor. Rated current: 16 A. Coil voltage: 240 V. Operating temperature: -20 to 50 C. RoHS compliant."}
    ]
)

# 2. Siemens Contactor (Family / Similar to Schneider)
add(
    "UGI-CONTACTOR-002",
    "Siemens",
    "3RT2015-1AP01",
    [
        {"name": "Siemens SIRIUS Product Datasheet", "type": "manufacturer_datasheet", "text": "Siemens SIRIUS 3RT2015-1AP01 Power Contactor. 3 poles, AC-3 rated. Current rating: 18 A. Coil voltage: 230 VAC 50 Hz. Power: 7.5 kW. Mounting type: DIN rail / screw. IP Rating: IP20. Operating temperature: -25 to 60 C. UL, CE, CSA, RoHS approved."}
    ]
)

# 3. ABB Circuit Breaker
add(
    "UGI-BREAKER-001",
    "ABB",
    "S203-C16",
    [
        {"name": "ABB System pro M compact Datasheet", "type": "manufacturer_datasheet", "text": "ABB S203-C16 Miniature Circuit Breaker MCB. Number of poles: 3. Rated current: 16 A. Voltage rating: 400 VAC. Breaking capacity: 6 kA. Trip curve: C. Mounting type: DIN rail. Operating temperature: -25 to 55 C. IP Rating: IP20. UL 1077, CE, RoHS certified."}
    ]
)

# 4. Ball Valve
add(
    "UGI-VALVE-001",
    "DemoFlow Industrial",
    "BV-050-SS304",
    [
        {"name": "DemoFlow Engineering Manual", "type": "manufacturer_datasheet", "text": "DemoFlow BV-050-SS304 Heavy Duty Ball Valve. Port size: 1/2 inch. Body material: 304 Stainless Steel. Seat material: PTFE. Working pressure: 1000 psi. Connection type: Female NPT threaded. Temperature rating: -20 to 180 C. ISO 9001, CE."}
    ]
)

# 5. Deep Groove Ball Bearing
add(
    "UGI-BEARING-001",
    "SKF",
    "6205-2RSH",
    [
        {"name": "SKF Rolling Bearings Master Catalog", "type": "manufacturer_datasheet", "text": "SKF 6205-2RSH Deep groove ball bearing. Inner diameter: 25 mm. Outer diameter: 52 mm. Width: 15 mm. Dynamic load: 14.8 kN. Static load: 7.8 kN. Max speed: 8500 rpm. Seal type: Contact seal NBR on both sides. Material: High carbon chromium steel. Weight: 0.13 kg."}
    ]
)

# 6. Baldor Electric Motor
add(
    "UGI-MOTOR-001",
    "Baldor-Reliance",
    "EM3554T",
    [
        {"name": "Baldor General Purpose Motor Spec", "type": "manufacturer_datasheet", "text": "Baldor EM3554T Industrial Electric Motor. Horsepower: 1.5 hp. Power: 1.1 kW. Rated voltage: 230/460 V. Rated current: 4.2/2.1 A. Speed: 1760 rpm. Frame: 145T. Efficiency: 86.5%. Enclosure: TEFC (Totally Enclosed Fan Cooled). Frequency: 60 Hz. Torque: 6.1 Nm. Weight: 18.1 kg. UL, CSA, CE."}
    ]
)

# 7. Omron Proximity Sensor
add(
    "UGI-SENSOR-001",
    "Omron Automation",
    "E2B-M12KS04-WP-B1",
    [
        {"name": "Omron Cylindrical Proximity Sensor Datasheet", "type": "manufacturer_datasheet", "text": "Omron E2B-M12KS04-WP-B1 Inductive Proximity Sensor. Sensing range: 4 mm. Supply voltage: 12 to 24 VDC. Output signal: PNP NO. Response time: 1.5 ms. IP Rating: IP67. Operating temperature: -25 to 70 C. Body material: Nickel-plated brass. UL, CE, RoHS."}
    ]
)

# 8. Phoenix Contact Industrial Relay
add(
    "UGI-RELAY-001",
    "Phoenix Contact",
    "RIF-1-RSC-LDP-24DC/2X21",
    [
        {"name": "Phoenix Contact Relay Module Datasheet", "type": "manufacturer_datasheet", "text": "Phoenix Contact RIFLINE complete Relay Module. Coil voltage: 24 VDC. Contact rating: 8 A. Number of poles: 2 (DPDT). Mounting type: DIN rail. Response time: 8 ms. Operating temperature: -40 to 70 C. IP Rating: IP20. UL, CSA, CE, RoHS."}
    ]
)

# Seed connectors
upsert_connector("CX1 / PIM Production", "CX1", "https://api.unilogcorp.com/cx1/v2", "ACTIVE", {"mode": "outbound_golden_record_sync", "auth_type": "bearer_token"})
upsert_connector("SAP S/4HANA ERP", "ERP", "https://sap.enterprise.internal/api/mm", "CONFIGURED", {"mode": "inventory_and_pricing_sync", "auth_type": "basic"})
upsert_connector("Akeneo Enterprise PIM", "CUSTOM", "https://pim.enterprise.internal/api/rest/v1", "CONFIGURED", {"mode": "catalog_syndication", "channel": "ecommerce_global"})

print("Enterprise demo catalog seeded successfully with 8 industrial Golden Records.")
