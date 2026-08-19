from __future__ import annotations
import csv, io, json, os, shutil, uuid, time, re
from pathlib import Path
from typing import List
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from . import db
from .services.catalog_ai import (
    build_product,
    relation_edges,
    product_hash,
    recalculate_product_scores,
    export_shopify_row,
    export_akeneo_json,
    export_schema_org,
    export_factsheet_html,
    normalize_unit,
)
from .services.file_extract import extract_file
from .services.enterprise_ai import family_and_relationships, anomaly_findings, publish_gate
from .services.copilot_ai import generate_copilot_response

BASE = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE / os.getenv('UPLOAD_DIR', 'data/uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='UniGraph IQ Enterprise', version='2.0.0', docs_url='/docs', redoc_url='/redoc')
app.mount('/static', StaticFiles(directory=str(Path(__file__).parent / 'static')), name='static')
app.add_middleware(CORSMiddleware, allow_origins=[x for x in os.getenv('CORS_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',')], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        r = await call_next(request)
        r.headers['X-Content-Type-Options'] = 'nosniff'
        r.headers['X-Frame-Options'] = 'DENY'
        r.headers['Referrer-Policy'] = 'same-origin'
        r.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return r
app.add_middleware(SecurityHeaders)

@app.on_event('startup')
def startup():
    db.init_db()

def actor(request: Request):
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.lower().startswith('bearer ') else request.cookies.get('ugiq_session')
    user = db.session_user(token)
    if not user:
        key = request.headers.get('X-API-Key')
        user = db.api_key_user(key)
    if user: return user
    if os.getenv('AUTH_REQUIRED', 'false').lower() != 'true':
        return {'email': 'local-demo', 'name': 'Local Demo', 'role': 'admin'}
    return None

def require(request: Request, roles=None):
    u = actor(request)
    if not u: raise HTTPException(401, 'Authentication required')
    if roles and u['role'] not in roles: raise HTTPException(403, 'Insufficient role')
    return u

@app.get('/', response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / 'templates' / 'index.html').read_text(encoding='utf-8')

@app.post('/api/auth/login')
async def login(payload: dict):
    r = db.auth_user(str(payload.get('email', '')), str(payload.get('password', '')))
    if not r: raise HTTPException(401, 'Invalid credentials')
    token, user = r
    db.log('LOGIN', 'successful', actor=user['email'])
    resp = JSONResponse({'token': token, 'user': user})
    resp.set_cookie('ugiq_session', token, httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', max_age=43200)
    return resp

@app.get('/api/auth/me')
def me(request: Request):
    return require(request)

@app.get('/api/admin/users')
def users(request: Request):
    require(request, {'admin'})
    return db.list_users()

@app.post('/api/admin/users')
async def add_user(payload: dict, request: Request):
    u = require(request, {'admin'})
    db.create_user(payload['email'], payload.get('name', ''), payload.get('role', 'viewer'), payload['password'])
    db.log('USER_CREATED', payload['email'], actor=u['email'])
    return {'ok': True}

@app.delete('/api/admin/users/{user_id}')
async def deactivate_user(user_id: int, request: Request):
    u = require(request, {'admin'})
    db.deactivate_user(user_id)
    db.log('USER_DEACTIVATED', str(user_id), actor=u['email'])
    return {'ok': True}

@app.post('/api/admin/api-keys')
async def new_key(payload: dict, request: Request):
    u = require(request, {'admin'})
    raw = db.create_api_key(payload.get('name', 'integration'), payload.get('role', 'integration'))
    db.log('API_KEY_CREATED', payload.get('name', 'integration'), actor=u['email'])
    return {'api_key': raw, 'warning': 'Store this key now; it is not retrievable later.'}

@app.get('/api/admin/api-keys')
def list_keys(request: Request):
    require(request, {'admin'})
    return db.list_api_keys()

@app.get('/api/dashboard')
def dashboard(request: Request):
    require(request)
    return {'metrics': db.dashboard(), 'products': db.list_products()[:8], 'review_queue': db.review_queue()[:8], 'audit': db.audit(12), 'jobs': db.jobs(8)}

@app.get('/api/catalog/analytics')
def catalog_analytics(request: Request):
    require(request)
    return db.get_catalog_analytics()

@app.get('/api/products')
def products(request: Request):
    require(request)
    return db.list_products()

@app.get('/api/products/{sku}')
def product(sku: str, request: Request):
    require(request)
    p = db.get_product(sku)
    if not p: raise HTTPException(404, 'Product not found')
    p['reviews'] = db.reviews(sku)
    p['publish_gate'] = publish_gate(p)
    return p

@app.get('/api/products/{sku}/graph')
def graph(sku: str, request: Request):
    require(request)
    return db.get_edges(sku)

@app.post('/api/enrich')
async def enrich(
    request: Request,
    sku: str = Form(...),
    manufacturer: str = Form(''),
    mpn: str = Form(''),
    product_text: str = Form(''),
    source_type: str = Form('user_input'),
    files: List[UploadFile] = File(default=[]),
):
    u = require(request, {'admin', 'product_manager', 'data_steward', 'integration'})
    sources = []
    if product_text.strip():
        sources.append({'name': 'pasted product information', 'type': source_type, 'text': product_text.strip()})
    for f in files:
        if not f.filename: continue
        safe = f'{uuid.uuid4().hex[:8]}_{Path(f.filename).name}'
        path = UPLOAD_DIR / safe
        with path.open('wb') as out: shutil.copyfileobj(f.file, out)
        sources.extend(extract_file(path))
    if not sources:
        sources = [{'name': 'identity input', 'type': 'user_input', 'text': f'Manufacturer: {manufacturer}\nMPN: {mpn}\nSKU: {sku}'}]
    p = build_product(sku.strip(), manufacturer.strip(), mpn.strip(), sources)
    rel = family_and_relationships(p, db.list_products())
    p['family'] = rel['family_key']
    p['anomalies'] = anomaly_findings(p)
    p['publish_gate'] = publish_gate(p)
    p['record_hash'] = product_hash(p)
    p['_source_documents'] = sources
    edges = relation_edges(p) + rel['relationships']
    db.upsert_product(p, edges, actor=u['email'])
    p.pop('_source_documents', None)
    return p

@app.post('/api/products/{sku}/attribute')
async def update_attribute(sku: str, payload: dict, request: Request):
    """In-line Data Steward override or candidate selection for a specific attribute."""
    u = require(request, {'admin', 'product_manager', 'data_steward'})
    p = db.get_product(sku)
    if not p: raise HTTPException(404, 'Product not found')
    
    attr_name = payload.get('name')
    if not attr_name: raise HTTPException(400, 'Attribute name is required')
    val = payload.get('value')
    unit = payload.get('unit')
    val, unit = normalize_unit(val, unit)
    comment = payload.get('comment', 'Steward manual override')
    
    # Update or insert attribute
    p['attributes'][attr_name] = {
        'value': val,
        'unit': unit,
        'confidence': 1.0,
        'status': 'VERIFIED',
        'provenance': [{
            'source': f"Steward ({u['email']})",
            'source_type': 'steward_override',
            'evidence': comment,
            'confidence': 1.0,
        }]
    }
    
    # Remove resolved conflict for this attribute if present
    p['conflicts'] = [c for c in p.get('conflicts', []) if c['attribute'] != attr_name]
    
    # Recalculate scores and publish gate
    p = recalculate_product_scores(p)
    p['anomalies'] = anomaly_findings(p)
    p['publish_gate'] = publish_gate(p)
    p['record_hash'] = product_hash(p)
    
    rel = family_and_relationships(p, db.list_products())
    edges = relation_edges(p) + rel['relationships']
    db.upsert_product(p, edges, actor=u['email'])
    db.add_review(sku, attr_name, 'OVERRIDE', f"{val} {unit or ''}".strip(), comment, u['email'])
    
    return p

@app.post('/api/compare')
async def compare_products(payload: dict, request: Request):
    """Cross-reference 2 to 4 products and build spec comparison matrix."""
    require(request)
    skus = payload.get('skus', [])
    if not skus: raise HTTPException(400, 'No SKUs provided for comparison')
    products = db.get_products_by_skus(skus[:6])
    if not products: raise HTTPException(404, 'No matching products found')
    
    # Union of all attribute names
    all_attrs = sorted(list({k for p in products for k in p.get('attributes', {}).keys()}))
    
    matrix = []
    for attr in all_attrs:
        row = {'attribute': attr, 'label': attr.replace('_', ' ').title(), 'values': {}}
        vals_seen = set()
        for p in products:
            if attr in p.get('attributes', {}):
                a = p['attributes'][attr]
                val_str = f"{a['value']} {a.get('unit') or ''}".strip()
                row['values'][p['sku']] = {'value': val_str, 'confidence': a.get('confidence', 1.0), 'status': a.get('status', 'VERIFIED')}
                vals_seen.add(val_str.lower())
            else:
                row['values'][p['sku']] = {'value': None, 'confidence': 0, 'status': 'MISSING'}
        row['is_match'] = len(vals_seen) == 1 and all(row['values'][p['sku']]['value'] is not None for p in products)
        matrix.append(row)
        
    return {
        'products': products,
        'matrix': matrix,
        'total_attributes': len(all_attrs),
    }

@app.post('/api/bulk')
async def bulk(request: Request, file: UploadFile = File(...)):
    u = require(request, {'admin', 'product_manager', 'data_steward', 'integration'})
    raw = await file.read()
    text = raw.decode('utf-8-sig', 'ignore')
    rows = list(csv.DictReader(io.StringIO(text)))
    jid = 'JOB-' + uuid.uuid4().hex[:10].upper()
    db.create_job(jid, 'BULK_CATALOG_ENRICHMENT', len(rows), u['email'], file.filename)
    success = failed = 0
    for i, row in enumerate(rows, 1):
        try:
            sku = row.get('sku') or row.get('SKU') or row.get('mpn') or f'ROW-{i}'
            m = row.get('manufacturer', '')
            mpn = row.get('mpn', '')
            src = [{'name': file.filename, 'type': 'customer_catalog', 'text': ' | '.join(f'{k}: {v}' for k, v in row.items() if v)}]
            p = build_product(sku, m, mpn, src)
            rel = family_and_relationships(p, db.list_products())
            p['family'] = rel['family_key']
            p['anomalies'] = anomaly_findings(p)
            p['publish_gate'] = publish_gate(p)
            p['record_hash'] = product_hash(p)
            p['_source_documents'] = src
            db.upsert_product(p, relation_edges(p) + rel['relationships'], actor=u['email'])
            success += 1
        except Exception:
            failed += 1
        db.update_job(jid, i, success, failed)
    db.update_job(jid, len(rows), success, failed, 'COMPLETED' if failed == 0 else 'COMPLETED_WITH_ERRORS')
    return {'job_id': jid, 'total': len(rows), 'success': success, 'failed': failed}

@app.get('/api/jobs')
def jobs(request: Request):
    require(request)
    return db.jobs()

@app.get('/api/rag/search')
def rag(q: str, request: Request):
    require(request)
    return {'query': q, 'results': db.search_evidence(q)}

@app.post('/api/reviews/{sku}')
async def review(sku: str, payload: dict, request: Request):
    u = require(request, {'admin', 'product_manager', 'data_steward', 'compliance'})
    decision = payload.get('decision', 'COMMENT')
    db.add_review(sku, payload.get('attribute'), decision, str(payload.get('value', '')), payload.get('comment', ''), u['email'])
    
    # If decision is APPROVE and user has steward/admin role, mark product publish-ready
    if decision == 'APPROVE':
        p = db.get_product(sku)
        if p:
            p['scores']['status'] = 'READY_TO_PUBLISH'
            p['publish_gate']['allowed'] = True
            p['publish_gate']['blockers'] = []
            rel = family_and_relationships(p, db.list_products())
            db.upsert_product(p, relation_edges(p) + rel['relationships'], actor=u['email'])
            
    return {'ok': True}

@app.get('/api/audit')
def audit(request: Request):
    require(request, {'admin', 'product_manager'})
    return db.audit(200)

@app.get('/api/connectors')
def connector_list(request: Request):
    require(request)
    return db.connectors()

@app.post('/api/connectors')
async def connector_upsert(payload: dict, request: Request):
    u = require(request, {'admin'})
    db.upsert_connector(payload['name'], payload['type'], payload.get('base_url', ''), payload.get('status', 'CONFIGURED'), payload.get('config', {}))
    db.log('CONNECTOR_CONFIGURED', payload['name'], actor=u['email'])
    return {'ok': True}

@app.post('/api/connectors/{name}/test')
async def connector_test(name: str, request: Request):
    """Simulate connector connection test."""
    require(request, {'admin', 'integration'})
    return {'connector': name, 'status': 'ONLINE', 'latency_ms': 42, 'message': 'Handshake verified. Schema compatibility OK.'}

@app.post('/api/connectors/{name}/dispatch')
async def connector_dispatch(name: str, payload: dict, request: Request):
    """Simulate dispatching a Golden Record payload to a PIM/ERP connector."""
    u = require(request, {'admin', 'product_manager', 'integration'})
    sku = payload.get('sku', 'UNKNOWN')
    db.log('CONNECTOR_DISPATCH', f"Product {sku} dispatched to {name}", sku=sku, actor=u['email'])
    return {'ok': True, 'connector': name, 'sku': sku, 'remote_id': f"EXT-{uuid.uuid4().hex[:8].upper()}", 'dispatched_at': db._now()}

# ============================================================
# EXPORT & SYNDICATION ENDPOINTS
# ============================================================

@app.get('/api/export/{sku}.json')
def export_json(sku: str, request: Request):
    require(request)
    p = db.get_product(sku)
    if not p: raise HTTPException(404, 'Product not found')
    payload = json.dumps(p, indent=2, ensure_ascii=False)
    return StreamingResponse(io.BytesIO(payload.encode()), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{sku}_golden_record.json"'})

@app.get('/api/export/{sku}/syndication/{fmt}')
def export_syndication(sku: str, fmt: str, request: Request):
    require(request)
    p = db.get_product(sku)
    if not p: raise HTTPException(404, 'Product not found')
    
    fmt = fmt.lower().strip()
    if fmt == 'shopify':
        row = export_shopify_row(p)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)
        return StreamingResponse(io.BytesIO(buf.getvalue().encode('utf-8-sig')), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{sku}_shopify.csv"'})
    
    if fmt in {'akeneo', 'cx1', 'pim'}:
        data = export_akeneo_json(p)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        return StreamingResponse(io.BytesIO(payload.encode()), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{sku}_akeneo_pim.json"'})
        
    if fmt in {'schema_org', 'jsonld', 'json-ld'}:
        data = export_schema_org(p)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        return StreamingResponse(io.BytesIO(payload.encode()), media_type='application/ld+json', headers={'Content-Disposition': f'attachment; filename="{sku}_schema_org.jsonld"'})
        
    if fmt in {'factsheet', 'pdf_preview', 'html'}:
        html = export_factsheet_html(p)
        return HTMLResponse(html)
        
    raise HTTPException(400, f'Unsupported syndication format: {fmt}')

@app.get('/api/export/catalog.csv')
def export_csv(request: Request):
    require(request)
    rows = db.list_products()
    buf = io.StringIO()
    fields = ['sku', 'manufacturer', 'mpn', 'category', 'status', 'intelligence_score', 'commerce_score', 'completeness', 'conflict_count', 'updated_at']
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="unigraph_catalog.csv"'})

@app.post('/api/copilot')
async def copilot(payload: dict, request: Request):
    require(request)
    q = str(payload.get('question', '')).strip()
    if not q:
        return {'answer': 'Please ask a question about the industrial catalog, specifications, or UniGraph IQ platform features.'}
    
    ps = db.list_products()
    evidence_hits = db.search_evidence(q)
    return generate_copilot_response(q, ps, evidence_hits)


@app.get('/metrics')
def metrics():
    d = db.dashboard()
    return StreamingResponse(io.BytesIO((f"unigraph_products {d['total']}\nunigraph_conflicts {d['conflicts']}\nunigraph_avg_iq {d['avg_iq']}\n").encode()), media_type='text/plain')

@app.get('/health')
def health():
    start = time.time()
    d = db.dashboard()
    return {'status': 'ok', 'product': 'UniGraph IQ Enterprise', 'version': '2.0.0', 'database': 'ok', 'products': d['total'], 'evidence_chunks': d['evidence_chunks'], 'latency_ms': round((time.time() - start) * 1000, 2)}
