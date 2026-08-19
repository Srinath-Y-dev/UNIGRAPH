from __future__ import annotations
import json, os, sqlite3, hashlib, secrets
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone, timedelta

DB_PATH = Path(os.getenv('DATABASE_PATH','data/unigraph.db'))

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB_PATH, timeout=30); c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA foreign_keys=ON'); return c

def _now(): return datetime.now(timezone.utc).isoformat()
def _hash(x:str): return hashlib.sha256(x.encode()).hexdigest()

def init_db():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY,manufacturer TEXT,mpn TEXT,category TEXT,status TEXT,intelligence_score REAL,commerce_score REAL,completeness REAL,conflict_count INTEGER,data_json TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS graph_edges(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT NOT NULL,source TEXT NOT NULL,relation TEXT NOT NULL,target TEXT NOT NULL,confidence REAL DEFAULT 1.0,evidence TEXT);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT,actor TEXT DEFAULT 'system',action TEXT NOT NULL,detail TEXT,ip TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,name TEXT,role TEXT NOT NULL,password_hash TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP,last_login TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS api_keys(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,key_hash TEXT UNIQUE NOT NULL,key_prefix TEXT NOT NULL,role TEXT DEFAULT 'integration',active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP,last_used TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,type TEXT NOT NULL,status TEXT NOT NULL,total INTEGER DEFAULT 0,processed INTEGER DEFAULT 0,success INTEGER DEFAULT 0,failed INTEGER DEFAULT 0,detail TEXT,created_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT NOT NULL,source_name TEXT,source_type TEXT,content TEXT NOT NULL,content_hash TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_evidence_sku ON evidence(sku);
        CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT NOT NULL,attribute TEXT,decision TEXT NOT NULL,value TEXT,comment TEXT,reviewer TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS connectors(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,type TEXT NOT NULL,base_url TEXT,status TEXT DEFAULT 'CONFIGURED',config_json TEXT DEFAULT '{}',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT,field TEXT,old_value TEXT,new_value TEXT,actor TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        # Lightweight forward migrations
        edge_cols={r['name'] for r in c.execute('PRAGMA table_info(graph_edges)').fetchall()}
        if 'confidence' not in edge_cols: c.execute('ALTER TABLE graph_edges ADD COLUMN confidence REAL DEFAULT 1.0')
        if 'evidence' not in edge_cols: c.execute('ALTER TABLE graph_edges ADD COLUMN evidence TEXT')
        # Sync Admin credentials from environment variables
        admin_pwd = os.getenv('ADMIN_PASSWORD', 'admin123!').strip()
        custom_email = os.getenv('ADMIN_EMAIL', '').strip().lower()
        
        # 1. Maintain admin@unigraph.local
        admin_local = c.execute("SELECT id FROM users WHERE lower(email)='admin@unigraph.local'").fetchone()
        if admin_local:
            c.execute('UPDATE users SET password_hash=?, active=1, role=? WHERE id=?', (_hash(admin_pwd), 'admin', admin_local['id']))
        else:
            c.execute('INSERT INTO users(email,name,role,password_hash) VALUES (?,?,?,?)', ('admin@unigraph.local', 'Administrator', 'admin', _hash(admin_pwd)))

        # 2. If a custom ADMIN_EMAIL is provided, sync that user too
        if custom_email and custom_email != 'admin@unigraph.local':
            custom_user = c.execute('SELECT id FROM users WHERE lower(email)=?', (custom_email,)).fetchone()
            if custom_user:
                c.execute('UPDATE users SET password_hash=?, active=1, role=? WHERE id=?', (_hash(admin_pwd), 'admin', custom_user['id']))
            else:
                c.execute('INSERT INTO users(email,name,role,password_hash) VALUES (?,?,?,?)', (custom_email, 'Administrator', 'admin', _hash(admin_pwd)))

def log(action, detail='', sku=None, actor='system', ip=None):
    with conn() as c: c.execute('INSERT INTO audit_log(sku,actor,action,detail,ip) VALUES (?,?,?,?,?)',(sku,actor,action,detail,ip))

def upsert_product(product:Dict[str,Any], edges:List[Dict[str,Any]], actor='system'):
    s=product['scores']
    with conn() as c:
        stored=dict(product); stored.pop('_source_documents',None)
        c.execute('''INSERT INTO products(sku,manufacturer,mpn,category,status,intelligence_score,commerce_score,completeness,conflict_count,data_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sku) DO UPDATE SET manufacturer=excluded.manufacturer,mpn=excluded.mpn,category=excluded.category,status=excluded.status,intelligence_score=excluded.intelligence_score,commerce_score=excluded.commerce_score,completeness=excluded.completeness,conflict_count=excluded.conflict_count,data_json=excluded.data_json,updated_at=excluded.updated_at''',(product['sku'],product['identity'].get('manufacturer'),product['identity'].get('mpn'),product['category'],s['status'],s['product_intelligence_score'],s['commerce_readiness'],s['completeness'],len(product.get('conflicts',[])),json.dumps(stored),product['updated_at']))
        c.execute('DELETE FROM graph_edges WHERE sku=?',(product['sku'],))
        c.executemany('INSERT INTO graph_edges(sku,source,relation,target,confidence,evidence) VALUES(?,?,?,?,?,?)',[(product['sku'],e['source'],e['relation'],e['target'],e.get('confidence',1.0),e.get('evidence')) for e in edges])
        c.execute('DELETE FROM evidence WHERE sku=?',(product['sku'],))
        for src in product.get('_source_documents',[]):
            txt=src.get('text',''); c.execute('INSERT INTO evidence(sku,source_name,source_type,content,content_hash) VALUES (?,?,?,?,?)',(product['sku'],src.get('name'),src.get('type'),txt,_hash(txt)))
        c.execute('INSERT INTO audit_log(sku,actor,action,detail) VALUES (?,?,?,?)',(product['sku'],actor,'PRODUCT_ENRICHED',f"{len(product.get('attributes',{}))} attributes; {len(product.get('conflicts',[]))} conflicts"))

def list_products():
    with conn() as c: return [dict(r) for r in c.execute('SELECT sku,manufacturer,mpn,category,status,intelligence_score,commerce_score,completeness,conflict_count,updated_at FROM products ORDER BY updated_at DESC').fetchall()]

def get_product(sku: str) -> Dict[str, Any] | None:
    with conn() as c:
        r=c.execute('SELECT data_json FROM products WHERE sku=?',(sku,)).fetchone(); return json.loads(r['data_json']) if r else None

def get_products_by_skus(skus: List[str]) -> List[Dict[str, Any]]:
    if not skus: return []
    placeholders = ','.join('?' for _ in skus)
    with conn() as c:
        rows = c.execute(f'SELECT data_json FROM products WHERE sku IN ({placeholders})', skus).fetchall()
        return [json.loads(r['data_json']) for r in rows]

def get_edges(sku=None):
    with conn() as c:
        q='SELECT source,relation,target,confidence,evidence FROM graph_edges'+(' WHERE sku=?' if sku else '')+' ORDER BY id DESC LIMIT 1000'; rows=c.execute(q,(sku,) if sku else ()).fetchall(); return [dict(r) for r in rows]

def dashboard():
    with conn() as c:
        r=c.execute("""SELECT COUNT(*) total,SUM(CASE WHEN status='READY_TO_PUBLISH' THEN 1 ELSE 0 END) ready,SUM(CASE WHEN status='REVIEW_REQUIRED' THEN 1 ELSE 0 END) review,SUM(CASE WHEN status='INSUFFICIENT_DATA' THEN 1 ELSE 0 END) insufficient,COALESCE(AVG(intelligence_score),0) avg_iq,COALESCE(AVG(commerce_score),0) avg_commerce,COALESCE(AVG(completeness),0) avg_completeness,COALESCE(SUM(conflict_count),0) conflicts FROM products""").fetchone(); d=dict(r); d['evidence_chunks']=c.execute('SELECT COUNT(*) n FROM evidence').fetchone()['n']; d['jobs']=c.execute('SELECT COUNT(*) n FROM jobs').fetchone()['n']; return d

def get_catalog_analytics():
    with conn() as c:
        categories = [dict(r) for r in c.execute('SELECT category, count(*) as count, round(avg(intelligence_score),1) as avg_iq FROM products GROUP BY category ORDER BY count DESC').fetchall()]
        statuses = [dict(r) for r in c.execute('SELECT status, count(*) as count FROM products GROUP BY status').fetchall()]
        completeness_buckets = {
            "90-100%": c.execute('SELECT count(*) n FROM products WHERE completeness >= 90').fetchone()['n'],
            "75-89%": c.execute('SELECT count(*) n FROM products WHERE completeness >= 75 AND completeness < 90').fetchone()['n'],
            "50-74%": c.execute('SELECT count(*) n FROM products WHERE completeness >= 50 AND completeness < 75').fetchone()['n'],
            "<50%": c.execute('SELECT count(*) n FROM products WHERE completeness < 50').fetchone()['n'],
        }
        top_mfrs = [dict(r) for r in c.execute('SELECT manufacturer, count(*) as count FROM products WHERE manufacturer IS NOT NULL AND manufacturer!="" GROUP BY manufacturer ORDER BY count DESC LIMIT 8').fetchall()]
        return {
            "categories": categories,
            "statuses": statuses,
            "completeness_buckets": completeness_buckets,
            "manufacturers": top_mfrs,
        }

def review_queue():
    with conn() as c: return [dict(r) for r in c.execute("SELECT sku,manufacturer,mpn,category,status,intelligence_score,commerce_score,completeness,conflict_count,updated_at FROM products WHERE status!='READY_TO_PUBLISH' OR conflict_count>0 ORDER BY conflict_count DESC,completeness ASC").fetchall()]

def audit(limit=50):
    with conn() as c: return [dict(r) for r in c.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT ?',(limit,)).fetchall()]

def auth_user(email,password):
    with conn() as c:
        r=c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND active=1',(email,)).fetchone()
        if not r or not secrets.compare_digest(r['password_hash'],_hash(password)): return None
        token=secrets.token_urlsafe(32); exp=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat(); c.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(_hash(token),r['id'],exp)); c.execute('UPDATE users SET last_login=? WHERE id=?',(_now(),r['id'])); return token, {k:r[k] for k in ['id','email','name','role']}

def session_user(token):
    if not token:return None
    with conn() as c:
        r=c.execute('SELECT u.id,u.email,u.name,u.role,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND u.active=1',(_hash(token),)).fetchone()
        if not r:return None
        if datetime.fromisoformat(r['expires_at'])<datetime.now(timezone.utc): return None
        return dict(r)

def create_user(email,name,role,password):
    if role not in {'admin','product_manager','data_steward','compliance','viewer','integration'}: raise ValueError('Invalid role')
    with conn() as c: c.execute('INSERT INTO users(email,name,role,password_hash) VALUES(?,?,?,?)',(email,name,role,_hash(password)))

def list_users():
    with conn() as c:return [dict(r) for r in c.execute('SELECT id,email,name,role,active,created_at,last_login FROM users ORDER BY id').fetchall()]

def create_api_key(name,role='integration'):
    raw='ugiq_'+secrets.token_urlsafe(28); pref=raw[:12]
    with conn() as c:c.execute('INSERT INTO api_keys(name,key_hash,key_prefix,role) VALUES(?,?,?,?)',(name,_hash(raw),pref,role))
    return raw

def api_key_user(raw):
    if not raw:return None
    with conn() as c:
        r=c.execute('SELECT id,name,role FROM api_keys WHERE key_hash=? AND active=1',(_hash(raw),)).fetchone()
        if r:c.execute('UPDATE api_keys SET last_used=? WHERE id=?',(_now(),r['id']))
        return {'email':f"apikey:{r['name']}",'name':r['name'],'role':r['role']} if r else None

def add_review(sku,attribute,decision,value,comment,reviewer):
    with conn() as c:c.execute('INSERT INTO reviews(sku,attribute,decision,value,comment,reviewer) VALUES(?,?,?,?,?,?)',(sku,attribute,decision,value,comment,reviewer)); c.execute('INSERT INTO audit_log(sku,actor,action,detail) VALUES(?,?,?,?)',(sku,reviewer,'REVIEW_DECISION',f'{attribute}:{decision} {comment}'))

def reviews(sku):
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM reviews WHERE sku=? ORDER BY id DESC',(sku,)).fetchall()]

def search_evidence(query,limit=20):
    terms=[t.lower() for t in query.split() if len(t)>2]
    if not terms: terms = [query.lower().strip()]
    with conn() as c: rows=c.execute('SELECT id,sku,source_name,source_type,content FROM evidence ORDER BY id DESC LIMIT 500').fetchall()
    scored=[]
    for r in rows:
        text=r['content'].lower(); score=sum(text.count(t) for t in terms)
        if score: scored.append((score,dict(r)))
    scored.sort(key=lambda x:x[0],reverse=True)
    out=[]
    for score,r in scored[:limit]:
        text=r.pop('content'); pos=min([text.lower().find(t) for t in terms if text.lower().find(t)>=0] or [0]); r['snippet']=text[max(0,pos-180):pos+420]; r['score']=score; out.append(r)
    return out

def create_job(job_id,jtype,total,creator,detail=''):
    with conn() as c:c.execute('INSERT INTO jobs(id,type,status,total,detail,created_by) VALUES(?,?,?,?,?,?)',(job_id,jtype,'RUNNING',total,detail,creator))

def update_job(job_id,processed,success,failed,status=None,detail=None):
    with conn() as c:c.execute('UPDATE jobs SET processed=?,success=?,failed=?,status=COALESCE(?,status),detail=COALESCE(?,detail),updated_at=CURRENT_TIMESTAMP WHERE id=?',(processed,success,failed,status,detail,job_id))

def jobs(limit=50):
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()]

def connectors():
    with conn() as c:return [dict(r) for r in c.execute('SELECT id,name,type,base_url,status,config_json,created_at,updated_at FROM connectors ORDER BY name').fetchall()]

def upsert_connector(name,ctype,base_url,status='CONFIGURED',config=None):
    with conn() as c:c.execute('''INSERT INTO connectors(name,type,base_url,status,config_json) VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET type=excluded.type,base_url=excluded.base_url,status=excluded.status,config_json=excluded.config_json,updated_at=CURRENT_TIMESTAMP''',(name,ctype,base_url,status,json.dumps(config or {})))

def list_api_keys():
    with conn() as c:return [dict(r) for r in c.execute('SELECT id,name,key_prefix,role,active,created_at,last_used FROM api_keys ORDER BY id DESC').fetchall()]

def deactivate_user(user_id):
    with conn() as c:c.execute('UPDATE users SET active=0 WHERE id=?',(user_id,))
