from __future__ import annotations
import re, math
from collections import defaultdict
from typing import Dict,Any,List

def token_set(s): return set(re.findall(r'[a-z0-9]+',str(s).lower()))
def similarity(a,b):
    A,B=token_set(a),token_set(b); return len(A&B)/max(1,len(A|B))

def family_and_relationships(product:Dict[str,Any], catalog:List[Dict[str,Any]]):
    sku=product['sku']; cat=product.get('category',''); mfg=(product.get('identity',{}).get('manufacturer') or '').lower(); mpn=str(product.get('identity',{}).get('mpn') or '')
    fam=re.sub(r'[-_ ]?\d+[a-z]*$','',mpn,flags=re.I) or mpn[:6]
    relationships=[]
    for p in catalog:
        if p['sku']==sku: continue
        score=0
        if p.get('category')==cat: score+=0.45
        if (p.get('manufacturer') or '').lower()==mfg and mfg: score+=0.25
        other=str(p.get('mpn') or '')
        score+=0.30*similarity(mpn,other)
        if score>=0.55:
            relation='SAME_PRODUCT_FAMILY' if fam and fam.lower() in other.lower() else 'SIMILAR_PRODUCT'
            relationships.append({'source':sku,'relation':relation,'target':p['sku'],'confidence':round(min(.98,score),2),'evidence':'category/manufacturer/MPN similarity'})
    return {'family_key':f'{mfg}:{fam}'.strip(':'),'relationships':sorted(relationships,key=lambda x:x['confidence'],reverse=True)[:12]}

def anomaly_findings(product:Dict[str,Any]):
    out=[]
    for name,a in product.get('attributes',{}).items():
        v=a.get('value')
        try:num=float(str(v).replace(',',''))
        except:continue
        if any(k in name for k in ['weight']) and num>10000: out.append({'severity':'HIGH','attribute':name,'message':'Weight is unusually large; verify unit/decimal.'})
        if any(k in name for k in ['voltage']) and num>100000: out.append({'severity':'HIGH','attribute':name,'message':'Voltage appears outside common catalog range.'})
        if any(k in name for k in ['temperature']) and abs(num)>2000: out.append({'severity':'HIGH','attribute':name,'message':'Temperature appears outside plausible product range.'})
    return out

def publish_gate(product):
    blockers=[]
    if product.get('conflicts'): blockers.append('unresolved attribute conflicts')
    if product.get('scores',{}).get('completeness',0)<70: blockers.append('attribute completeness below 70%')
    if product.get('scores',{}).get('average_confidence',0)<75: blockers.append('average confidence below 75%')
    return {'allowed':not blockers,'blockers':blockers,'policy':'ENTERPRISE_DEFAULT_V1'}
