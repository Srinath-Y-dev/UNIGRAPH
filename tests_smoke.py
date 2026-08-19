import os, tempfile
fd, path = tempfile.mkstemp(suffix='.db')
os.close(fd)
os.unlink(path)
os.environ['DATABASE_PATH'] = path

from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

init_db()
c = TestClient(app)

# 1. Health & Dashboard
assert c.get('/health').status_code == 200
assert c.get('/api/dashboard').status_code == 200
assert c.get('/api/catalog/analytics').status_code == 200

# 2. Enrich Products
r1 = c.post('/api/enrich', data={
    'sku': 'SMOKE-001',
    'manufacturer': 'Schneider Electric',
    'mpn': 'LC1D18',
    'product_text': 'Schneider LC1D18 contactor. Poles: 3. Coil voltage: 220 VAC. Current rating: 18 A. Operating temperature: -5 to 60 C. UL, CE, RoHS.',
    'source_type': 'manufacturer_datasheet'
})
assert r1.status_code == 200, r1.text
p1 = r1.json()
assert p1['category'] == 'Contactor'
assert p1['taxonomy']['unspsc'] == '39121529'

r2 = c.post('/api/enrich', data={
    'sku': 'SMOKE-002',
    'manufacturer': 'Siemens',
    'mpn': '3RT2015',
    'product_text': 'Siemens 3RT2015 contactor. 3 poles. Coil voltage: 230 VAC. Current rating: 18 A. UL, CE, CSA.',
    'source_type': 'manufacturer_datasheet'
})
assert r2.status_code == 200, r2.text

# 3. Product Graph
assert c.get('/api/products/SMOKE-001/graph').status_code == 200

# 4. In-Line Attribute Override & Conflict Resolution
r_attr = c.post('/api/products/SMOKE-001/attribute', json={
    'name': 'voltage_rating',
    'value': 240,
    'unit': 'V',
    'comment': 'Steward primary verification'
})
assert r_attr.status_code == 200, r_attr.text
p_updated = r_attr.json()
assert p_updated['attributes']['voltage_rating']['value'] == 240
assert p_updated['attributes']['voltage_rating']['status'] == 'VERIFIED'

# 5. Product Cross-Reference Comparison Matrix
r_comp = c.post('/api/compare', json={'skus': ['SMOKE-001', 'SMOKE-002']})
assert r_comp.status_code == 200, r_comp.text
comp_data = r_comp.json()
assert len(comp_data['products']) == 2
assert comp_data['total_attributes'] > 0

# 6. Multi-Channel Syndication Exports
assert c.get('/api/export/SMOKE-001.json').status_code == 200
assert c.get('/api/export/SMOKE-001/syndication/shopify').status_code == 200
assert c.get('/api/export/SMOKE-001/syndication/akeneo').status_code == 200
assert c.get('/api/export/SMOKE-001/syndication/schema_org').status_code == 200
assert c.get('/api/export/SMOKE-001/syndication/factsheet').status_code == 200
assert c.get('/api/export/catalog.csv').status_code == 200

# 7. Connectors Test & Dispatch Simulation
c.post('/api/connectors', json={'name': 'CX1 Demo', 'type': 'CX1', 'base_url': 'https://example.invalid'})
assert c.post('/api/connectors/CX1%20Demo/test').status_code == 200
assert c.post('/api/connectors/CX1%20Demo/dispatch', json={'sku': 'SMOKE-001'}).status_code == 200

# 8. Copilot Natural Language & Project Intelligence Queries
r_cop1 = c.post('/api/copilot', json={'question': 'show contactors'})
assert r_cop1.status_code == 200
assert 'answer' in r_cop1.json()

r_cop2 = c.post('/api/copilot', json={'question': 'what is ready to publish?'})
assert r_cop2.status_code == 200
assert 'answer' in r_cop2.json()

r_cop3 = c.post('/api/copilot', json={'question': 'what is unigraph iq enterprise and how does QA Guardian work?'})
assert r_cop3.status_code == 200
assert len(r_cop3.json().get('answer', '')) > 20

r_cop4 = c.post('/api/copilot', json={'question': 'show products with attribute conflicts'})
assert r_cop4.status_code == 200
assert 'answer' in r_cop4.json()

r_cop5 = c.post('/api/copilot', json={'question': 'show source evidence for voltage'})
assert r_cop5.status_code == 200

r_cop6 = c.post('/api/copilot', json={'question': 'SMOKE-001'})
assert r_cop6.status_code == 200
assert 'SMOKE-001' in r_cop6.json().get('answer', '') or len(r_cop6.json().get('products', [])) > 0

assert c.get('/metrics').status_code == 200

print('All UniGraph IQ Enterprise 2.0 smoke tests & upgraded features passed successfully!')
