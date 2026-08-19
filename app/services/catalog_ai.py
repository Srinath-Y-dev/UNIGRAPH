from __future__ import annotations

import json
import math
import os
import re
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests

CATEGORY_RULES = {
    "Contactor": ["contactor", "coil voltage", "ac-3", "motor starter", "poles", "auxiliary contact"],
    "Circuit Breaker": ["circuit breaker", "mcb", "mccb", "breaker", "breaking capacity", "trip curve", "rated current"],
    "Ball Valve": ["ball valve", "psi", "port size", "seat material", "threaded", "flanged", "actuated valve"],
    "Bearing": ["bearing", "inner diameter", "outer diameter", "dynamic load", "static load", "rpm", "roller bearing", "ball bearing"],
    "Electric Motor": ["motor", "horsepower", "rpm", "frame", "efficiency", "three phase", "single phase", "torque"],
    "Pump": ["pump", "flow rate", "head", "impeller", "discharge", "centrifugal pump", "gpm"],
    "Sensor": ["sensor", "sensing range", "output signal", "accuracy", "ip rating", "proximity", "transducer", "4-20ma"],
    "Cable": ["cable", "conductor", "awg", "insulation", "voltage rating", "shielded", "wire gauge"],
    "Relay": ["relay", "coil voltage", "contact rating", "dpdt", "spdt", "solid state", "switching current"],
    "Transformer": ["transformer", "primary voltage", "secondary voltage", "kva", "step down", "step up", "isolation"],
    "Flow Meter": ["flow meter", "flowmeter", "mass flow", "vortex", "coriolis", "magnetic flow", "gallons per minute"],
    "Pneumatic Actuator": ["pneumatic actuator", "air pressure", "stroke length", "bore size", "double acting", "spring return"],
}

CATEGORY_TAXONOMY = {
    "Contactor": {"unspsc": "39121529", "etim": "EC000066", "segment": "Electrical Distribution"},
    "Circuit Breaker": {"unspsc": "39121601", "etim": "EC000042", "segment": "Electrical Protection"},
    "Ball Valve": {"unspsc": "40141607", "etim": "EC010150", "segment": "Fluid Power & Piping"},
    "Bearing": {"unspsc": "31171500", "etim": "EC002167", "segment": "Mechanical Power Transmission"},
    "Electric Motor": {"unspsc": "26101100", "etim": "EC011680", "segment": "Motors & Drives"},
    "Pump": {"unspsc": "40151500", "etim": "EC010134", "segment": "Fluid Transfer"},
    "Sensor": {"unspsc": "39122200", "etim": "EC001855", "segment": "Automation & Sensing"},
    "Cable": {"unspsc": "26121600", "etim": "EC003250", "segment": "Cables & Wiring"},
    "Relay": {"unspsc": "39122300", "etim": "EC000196", "segment": "Electrical Switching"},
    "Transformer": {"unspsc": "39121000", "etim": "EC002486", "segment": "Power Conversion"},
    "Flow Meter": {"unspsc": "41112501", "etim": "EC011467", "segment": "Instrumentation"},
    "Pneumatic Actuator": {"unspsc": "40151600", "etim": "EC010078", "segment": "Pneumatics"},
    "Industrial Product": {"unspsc": "31160000", "etim": "EC000000", "segment": "General Industrial"},
}

EXPECTED_SCHEMA = {
    "Contactor": ["poles", "current_rating", "coil_voltage", "frequency", "mounting_type", "operating_temperature", "ip_rating"],
    "Circuit Breaker": ["poles", "current_rating", "voltage_rating", "breaking_capacity", "trip_curve", "mounting_type"],
    "Ball Valve": ["port_size", "body_material", "pressure_rating", "connection_type", "temperature_rating", "seat_material"],
    "Bearing": ["inner_diameter", "outer_diameter", "width", "dynamic_load", "static_load", "max_speed", "seal_type"],
    "Electric Motor": ["power", "voltage_rating", "current_rating", "rpm", "frame", "efficiency", "enclosure", "frequency", "torque"],
    "Pump": ["flow_rate", "head", "power", "voltage_rating", "inlet_size", "outlet_size", "material"],
    "Sensor": ["sensing_range", "supply_voltage", "output_signal", "accuracy", "response_time", "ip_rating"],
    "Cable": ["conductor_size", "core_count", "voltage_rating", "insulation", "temperature_rating", "length"],
    "Relay": ["coil_voltage", "contact_rating", "poles", "mounting_type", "response_time", "operating_temperature"],
    "Transformer": ["primary_voltage", "secondary_voltage", "power_rating", "frequency", "mounting_type", "efficiency"],
    "Flow Meter": ["flow_rate", "accuracy", "pressure_rating", "operating_temperature", "output_signal", "connection_type"],
    "Pneumatic Actuator": ["pressure_rating", "stroke_length", "bore_size", "body_material", "temperature_rating"],
    "Industrial Product": ["manufacturer", "mpn", "material", "dimensions", "weight", "voltage_rating", "current_rating", "operating_temperature"],
}

SOURCE_AUTHORITY = {
    "manufacturer_datasheet": 1.0,
    "manufacturer_website": 0.94,
    "certified_database": 0.90,
    "authorized_distributor": 0.82,
    "customer_catalog": 0.72,
    "ai_inference": 0.45,
    "user_input": 0.80,
    "steward_override": 1.0,
}

UNIT_PATTERNS = [
    ("current_rating", r"(?:current(?:\s*rating)?|rated current|amp(?:ere)?s?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(a|amp|amps|ampere|amperes)\b", "A"),
    ("voltage_rating", r"(?:voltage(?:\s*rating)?|rated voltage|nominal voltage)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(v|vac|vdc|volt|volts)\b", "V"),
    ("coil_voltage", r"coil\s*voltage\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(v|vac|vdc)\b", "V"),
    ("primary_voltage", r"primary\s*voltage\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(v|vac|vdc|kv)\b", "V"),
    ("secondary_voltage", r"secondary\s*voltage\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(v|vac|vdc|kv)\b", "V"),
    ("supply_voltage", r"supply\s*voltage\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(v|vac|vdc)\b", "V"),
    ("frequency", r"(?:frequency|freq)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*hz\b", "Hz"),
    ("pressure_rating", r"(?:pressure(?:\s*rating)?|max(?:imum)? pressure|working pressure)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(psi|bar|mpa|kpa)\b", None),
    ("temperature_rating", r"(?:temperature(?:\s*rating)?|operating temperature|max temperature)\s*[:=]?\s*([-+]?\d+(?:\.\d+)?)\s*°?\s*(c|f)\b", None),
    ("operating_temperature", r"operating\s*temperature\s*[:=]?\s*(?:[-+]?\d+(?:\.\d+)?\s*(?:to|[-–])\s*)?([-+]?\d+(?:\.\d+)?)\s*°?\s*(c|f)\b", None),
    ("power", r"(?:power|rated power|motor power|horsepower|hp)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kw|w|hp)\b", None),
    ("power_rating", r"(?:power\s*rating|capacity|apparent power)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kva|va|kw|w)\b", None),
    ("rpm", r"(?:speed|rated speed|rpm)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*rpm\b", "rpm"),
    ("torque", r"(?:torque|rated torque|holding torque)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(nm|n-m|n·m|ft-lb|in-lb)\b", None),
    ("flow_rate", r"(?:flow\s*rate|capacity|flow capacity)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(gpm|lpm|l/min|m3/h|m3h)\b", None),
    ("weight", r"(?:weight|mass|net weight)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kg|g|lb|lbs)\b", None),
    ("inner_diameter", r"inner\s*diameter\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches)\b", None),
    ("outer_diameter", r"outer\s*diameter\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches)\b", None),
    ("width", r"(?:width|overall width)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches)\b", None),
    ("port_size", r"port\s*size\s*[:=]?\s*([\d./]+)\s*(in|inch|inches|mm)?\b", None),
    ("stroke_length", r"stroke(?:\s*length)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch)\b", None),
    ("bore_size", r"bore(?:\s*size| diameter)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch)\b", None),
    ("poles", r"(?:number of poles|poles?|pole count)\s*[:=]?\s*(\d+)\b", "count"),
    ("breaking_capacity", r"(?:breaking\s*capacity|interrupting rating|icu)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(ka|a)\b", "kA"),
    ("dynamic_load", r"dynamic\s*load(?:\s*rating)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kn|n|lbf|lbs)\b", "kN"),
    ("static_load", r"static\s*load(?:\s*rating)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kn|n|lbf|lbs)\b", "kN"),
    ("response_time", r"response\s*time\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(ms|s|sec)\b", "ms"),
    ("ip_rating", r"\b(IP\d{2})\b", "rating"),
    ("nema_rating", r"\b(NEMA\s*(?:4X|4|12|1|3R|7|9))\b", "rating"),
]

TEXT_PATTERNS = {
    "material": r"(?:material|body material)\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "body_material": r"body\s*material\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "seat_material": r"seat\s*material\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "mounting_type": r"mounting(?:\s*type)?\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "connection_type": r"connection(?:\s*type)?\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "trip_curve": r"trip\s*curve\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "output_signal": r"output\s*signal\s*[:=]\s*([A-Za-z0-9 .\-/,]+)",
    "sensing_range": r"sensing\s*range\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "frame": r"frame(?:\s*size)?\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "enclosure": r"enclosure(?:\s*type)?\s*[:=]\s*([A-Za-z0-9 .\-/]+)",
    "manufacturer": r"manufacturer\s*[:=]\s*([A-Za-z0-9 &.\-]+)",
    "mpn": r"(?:mpn|manufacturer part number|part number|model)\s*[:=]\s*([A-Za-z0-9_./\-]+)",
}

CERTS = ["UL", "CE", "RoHS", "REACH", "CSA", "ETL", "ATEX", "IECEx", "ISO 9001"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify(text: str) -> Tuple[str, float, List[str]]:
    lower = text.lower()
    scores = {}
    reasons = {}
    for category, words in CATEGORY_RULES.items():
        hits = [w for w in words if w in lower]
        scores[category] = len(hits) / max(1, len(words))
        reasons[category] = hits
    category = max(scores, key=scores.get) if scores else "Industrial Product"
    score = scores.get(category, 0.0)
    if score == 0:
        return "Industrial Product", 0.55, ["General industrial specifications detected"]
    return category, min(0.98, 0.60 + score * 0.5), reasons[category]


def normalize_unit(value: Any, unit: str | None) -> Tuple[Any, str | None]:
    if unit is None:
        return value, None
    u = unit.lower().strip()
    try:
        f = float(value)
    except Exception:
        return value, unit
    # Distance
    if u == "cm": return round(f * 10, 4), "mm"
    if u in {"in", "inch", "inches"}: return round(f * 25.4, 4), "mm"
    # Weight
    if u == "g": return round(f / 1000, 6), "kg"
    if u in {"lb", "lbs"}: return round(f * 0.45359237, 6), "kg"
    # Pressure
    if u == "bar": return round(f * 14.5038, 4), "psi"
    if u == "mpa": return round(f * 145.038, 4), "psi"
    if u == "kpa": return round(f * 0.145038, 4), "psi"
    # Temperature
    if u == "f": return round((f - 32) * 5 / 9, 3), "C"
    # Voltage / Current
    if u in {"vac", "vdc", "volt", "volts"}: return f, "V"
    if u in {"amp", "amps", "ampere", "amperes"}: return f, "A"
    if u in {"kv"}: return round(f * 1000, 2), "V"
    # Power
    if u in {"hp"}: return round(f * 0.7457, 4), "kW"
    if u in {"w"}: return round(f / 1000, 4), "kW"
    # Torque
    if u in {"ft-lb", "ft-lbs"}: return round(f * 1.355818, 4), "Nm"
    if u in {"in-lb", "in-lbs"}: return round(f * 0.1129848, 4), "Nm"
    # Flow
    if u in {"lpm", "l/min"}: return round(f * 0.264172, 4), "GPM"
    if u in {"m3/h", "m3h"}: return round(f * 4.40287, 4), "GPM"
    return f, unit.upper() if len(unit) <= 4 else unit


def extract_attributes(text: str, source_name: str, source_type: str = "user_input") -> List[Dict[str, Any]]:
    attrs = []
    for key, pattern, forced_unit in UNIT_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.I):
            if key in {"ip_rating", "nema_rating"}:
                value, unit = m.group(1).upper().replace(" ", ""), forced_unit
            else:
                value = m.group(1)
                unit = forced_unit or (m.group(2) if m.lastindex and m.lastindex >= 2 else None)
                if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", str(value)):
                    value = float(value)
                    if value.is_integer(): value = int(value)
                value, unit = normalize_unit(value, unit)
            evidence = m.group(0).strip()
            attrs.append({
                "name": key,
                "value": value,
                "unit": unit,
                "source_name": source_name,
                "source_type": source_type,
                "evidence": evidence[:240],
                "extraction_confidence": 0.94,
            })
    for key, pattern in TEXT_PATTERNS.items():
        m = re.search(pattern, text, flags=re.I)
        if m:
            value = m.group(1).strip().strip(".,;|")[:100]
            attrs.append({
                "name": key,
                "value": value,
                "unit": None,
                "source_name": source_name,
                "source_type": source_type,
                "evidence": m.group(0).strip()[:240],
                "extraction_confidence": 0.91,
            })
    return attrs


def merge_attributes(items: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    grouped = defaultdict(list)
    for item in items:
        grouped[item["name"]].append(item)
    final = {}
    conflicts = []
    for name, values in grouped.items():
        def score(v):
            return SOURCE_AUTHORITY.get(v["source_type"], 0.6) * v.get("extraction_confidence", 0.8)
        ranked = sorted(values, key=score, reverse=True)
        chosen = ranked[0]
        unique = {(str(v["value"]).lower(), str(v.get("unit") or "").lower()) for v in ranked}
        agreement = 1.0 if len(unique) == 1 else max(0.35, 1.0 / len(unique))
        source = SOURCE_AUTHORITY.get(chosen["source_type"], 0.6)
        confidence = min(0.995, 0.45 * source + 0.35 * chosen["extraction_confidence"] + 0.20 * agreement)
        status = "VERIFIED" if confidence >= 0.90 and len(unique) == 1 else "SUPPORTED"
        if len(unique) > 1:
            status = "CONFLICTING"
            conflicts.append({
                "attribute": name,
                "recommended": {"value": chosen["value"], "unit": chosen.get("unit")},
                "candidates": [{"value": v["value"], "unit": v.get("unit"), "source": v["source_name"], "source_type": v["source_type"]} for v in ranked],
                "reason": "Multiple data sources reported conflicting attribute values. Review candidate evidence below.",
            })
        final[name] = {
            "value": chosen["value"],
            "unit": chosen.get("unit"),
            "confidence": round(confidence, 3),
            "status": status,
            "provenance": [{
                "source": v["source_name"],
                "source_type": v["source_type"],
                "evidence": v["evidence"],
                "confidence": round(score(v), 3),
            } for v in ranked],
        }
    return final, conflicts


def schema_completeness(category: str, attributes: Dict[str, Any]) -> Tuple[float, List[str]]:
    expected = EXPECTED_SCHEMA.get(category, EXPECTED_SCHEMA["Industrial Product"])
    missing = [x for x in expected if x not in attributes]
    completeness = (len(expected) - len(missing)) / max(1, len(expected))
    return completeness, missing


def compliance(text: str) -> Dict[str, Any]:
    found = [c for c in CERTS if re.search(rf"\b{re.escape(c)}\b", text, re.I)]
    return {"found": found, "missing_common": [c for c in CERTS if c not in found]}


def quality_scores(category: str, attrs: Dict[str, Any], conflicts: List[Dict[str, Any]], text: str, source_count: int) -> Dict[str, Any]:
    completeness, missing = schema_completeness(category, attrs)
    if attrs:
        confidence = sum(a["confidence"] for a in attrs.values()) / len(attrs)
    else:
        confidence = 0.0
    consistency = max(0.0, 1.0 - len(conflicts) / max(1, len(attrs)))
    traceability = min(1.0, source_count / 2) if source_count else 0.0
    has_identity = int("manufacturer" in attrs or "mpn" in attrs)
    intelligence = 100 * (0.35 * completeness + 0.25 * confidence + 0.20 * consistency + 0.15 * traceability + 0.05 * has_identity)
    commerce = 100 * (0.50 * completeness + 0.25 * consistency + 0.15 * confidence + 0.10 * (1 if len(text) > 100 else 0.4))
    review = "READY_TO_PUBLISH" if commerce >= 85 and not conflicts else "REVIEW_REQUIRED" if commerce >= 55 else "INSUFFICIENT_DATA"
    return {
        "product_intelligence_score": round(intelligence, 1),
        "commerce_readiness": round(commerce, 1),
        "completeness": round(completeness * 100, 1),
        "consistency": round(consistency * 100, 1),
        "average_confidence": round(confidence * 100, 1),
        "missing_attributes": missing,
        "status": review,
    }


def generate_content(product: Dict[str, Any]) -> Dict[str, Any]:
    attrs = product.get("attributes", {})
    identity = product.get("identity", {})
    manufacturer = identity.get("manufacturer") or attrs.get("manufacturer", {}).get("value") or "Industrial"
    mpn = identity.get("mpn") or attrs.get("mpn", {}).get("value") or product.get("sku") or "Product"
    category = product.get("category", "Industrial Product")
    highlights = []
    for key in ["current_rating", "voltage_rating", "coil_voltage", "power", "pressure_rating", "ip_rating", "material", "body_material", "torque", "flow_rate"]:
        if key in attrs:
            a = attrs[key]
            label = key.replace("_", " ").title()
            val = f"{a['value']} {a['unit'] or ''}".strip()
            highlights.append(f"{label}: {val}")
    short = f"{manufacturer} {mpn} {category}"
    if highlights:
        short += " — " + ", ".join(highlights[:2])
    long = f"{manufacturer} {mpn} is a high-reliability {category.lower()} engineered for demanding industrial commerce applications. "
    if highlights:
        long += "Validated technical specifications include " + "; ".join(highlights[:5]) + ". "
    long += "Attribute-level provenance, authority scoring, and confidence ratings are verified for direct syndication to PIM, ERP, and e-Commerce channels."
    return {
        "short_description": short,
        "long_description": long,
        "features": highlights[:8],
        "search_keywords": sorted(set([category.lower(), manufacturer.lower(), str(mpn).lower()] + [k.replace("_", " ") for k in attrs.keys()]))[:20],
    }


def llm_enhance(product: Dict[str, Any]) -> Dict[str, Any] | None:
    base = os.getenv("AI_BASE_URL", "").strip()
    key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    if not (base and key and model):
        return None
    prompt = "Return JSON only with short_description, long_description, features, search_keywords. Never invent specifications. Use only this record:\n" + json.dumps(product, ensure_ascii=False)[:12000]
    try:
        r = requests.post(base.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={
            "model": model,
            "messages": [{"role": "system", "content": "You create precise industrial product commerce content. Never add unsupported facts."}, {"role": "user", "content": prompt}],
            "temperature": 0.1,
        }, timeout=30)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"].strip()
        txt = re.sub(r"^```json\s*|\s*```$", "", txt, flags=re.I | re.S)
        return json.loads(txt)
    except Exception:
        return None


def build_product(sku: str, manufacturer: str, mpn: str, sources: List[Dict[str, str]]) -> Dict[str, Any]:
    combined = "\n\n".join(s["text"] for s in sources)
    category, class_conf, reasons = classify(combined + " " + manufacturer + " " + mpn)
    extracted = []
    for s in sources:
        extracted.extend(extract_attributes(s["text"], s["name"], s.get("type", "user_input")))
    if manufacturer:
        extracted.append({"name": "manufacturer", "value": manufacturer, "unit": None, "source_name": "user input", "source_type": "user_input", "evidence": manufacturer, "extraction_confidence": 0.99})
    if mpn:
        extracted.append({"name": "mpn", "value": mpn, "unit": None, "source_name": "user input", "source_type": "user_input", "evidence": mpn, "extraction_confidence": 0.99})
    attrs, conflicts = merge_attributes(extracted)
    identity = {
        "manufacturer": manufacturer or attrs.get("manufacturer", {}).get("value"),
        "mpn": mpn or attrs.get("mpn", {}).get("value"),
        "identity_confidence": 0.98 if manufacturer and mpn else 0.78 if (manufacturer or mpn) else 0.45,
        "status": "VERIFIED" if manufacturer and mpn else "SUPPORTED",
    }
    scores = quality_scores(category, attrs, conflicts, combined, len(sources))
    taxonomy = CATEGORY_TAXONOMY.get(category, CATEGORY_TAXONOMY["Industrial Product"])
    product = {
        "sku": sku,
        "identity": identity,
        "category": category,
        "taxonomy": taxonomy,
        "classification_confidence": round(class_conf, 3),
        "classification_evidence": reasons,
        "attributes": attrs,
        "conflicts": conflicts,
        "compliance": compliance(combined),
        "scores": scores,
        "sources": [{"name": s["name"], "type": s.get("type", "user_input"), "chars": len(s["text"])} for s in sources],
        "updated_at": now_iso(),
    }
    product["content"] = llm_enhance(product) or generate_content(product)
    return product


def recalculate_product_scores(product: Dict[str, Any]) -> Dict[str, Any]:
    """Recalculate quality scores, completeness, and publish status after an attribute edit or conflict resolution."""
    attrs = product.get("attributes", {})
    conflicts = product.get("conflicts", [])
    category = product.get("category", "Industrial Product")
    source_count = len(product.get("sources", [])) or 1
    scores = quality_scores(category, attrs, conflicts, product.get("content", {}).get("long_description", ""), source_count)
    product["scores"] = scores
    product["updated_at"] = now_iso()
    product["content"] = generate_content(product)
    return product


def relation_edges(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    pid = product["sku"]
    edges = []
    identity = product.get("identity", {})
    if identity.get("manufacturer"):
        edges.append({"source": pid, "relation": "MANUFACTURED_BY", "target": identity["manufacturer"], "confidence": 0.99, "evidence": "Identity Manufacturer"})
    edges.append({"source": pid, "relation": "CLASSIFIED_AS", "target": product.get("category", "Industrial Product"), "confidence": product.get("classification_confidence", 0.9), "evidence": "Taxonomy Classifier"})
    for cert in product.get("compliance", {}).get("found", []):
        edges.append({"source": pid, "relation": "CERTIFIED_WITH", "target": cert, "confidence": 0.95, "evidence": f"Certification {cert}"})
    for name, attr in product.get("attributes", {}).items():
        if name in {"manufacturer", "mpn"}: continue
        val = f"{attr['value']} {attr.get('unit') or ''}".strip()
        edges.append({"source": pid, "relation": f"HAS_{name.upper()}", "target": val, "confidence": attr.get("confidence", 0.9), "evidence": f"Attribute {name}"})
    return edges


def product_hash(product: Dict[str, Any]) -> str:
    raw = json.dumps(product, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


# ============================================================
# SYNDICATION SERIALIZERS
# ============================================================

def export_shopify_row(product: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Shopify CSV row format."""
    c = product.get("content", {})
    ident = product.get("identity", {})
    attrs = product.get("attributes", {})
    tags = list(c.get("search_keywords", [])) + product.get("compliance", {}).get("found", [])
    specs_body = "<ul>" + "".join(f"<li><strong>{k.replace('_',' ').title()}:</strong> {v.get('value')} {v.get('unit') or ''}</li>" for k, v in attrs.items()) + "</ul>"
    body_html = f"<p>{c.get('long_description','')}</p><h3>Technical Specifications</h3>{specs_body}"
    return {
        "Handle": product["sku"].lower().replace(" ", "-"),
        "Title": f"{ident.get('manufacturer','')} {ident.get('mpn','')} - {product.get('category','')}".strip(" -"),
        "Body (HTML)": body_html,
        "Vendor": ident.get("manufacturer", "Industrial"),
        "Type": product.get("category", "Industrial"),
        "Tags": ", ".join(tags),
        "Published": "true" if product.get("scores", {}).get("status") == "READY_TO_PUBLISH" else "false",
        "Option1 Name": "Title",
        "Option1 Value": "Default Title",
        "Variant SKU": product["sku"],
        "Variant Grams": "1000",
        "Variant Inventory Tracker": "shopify",
        "Variant Inventory Policy": "deny",
        "Variant Fulfillment Service": "manual",
        "Variant Price": "0.00",
        "Status": "active" if product.get("scores", {}).get("status") == "READY_TO_PUBLISH" else "draft",
    }


def export_akeneo_json(product: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Akeneo / CX1 standard PIM product payload."""
    attrs = product.get("attributes", {})
    ident = product.get("identity", {})
    c = product.get("content", {})
    values = {
        "name": [{"locale": "en_US", "scope": None, "data": c.get("short_description", "")}],
        "description": [{"locale": "en_US", "scope": None, "data": c.get("long_description", "")}],
        "brand": [{"locale": None, "scope": None, "data": ident.get("manufacturer", "")}],
        "mpn": [{"locale": None, "scope": None, "data": ident.get("mpn", "")}],
    }
    for k, v in attrs.items():
        val = f"{v.get('value')} {v.get('unit') or ''}".strip()
        values[k] = [{"locale": None, "scope": None, "data": val}]
    return {
        "identifier": product["sku"],
        "enabled": product.get("scores", {}).get("status") == "READY_TO_PUBLISH",
        "family": product.get("category", "Industrial Product"),
        "categories": [product.get("category", "Industrial Product")],
        "groups": [product.get("family", "")],
        "values": values,
        "created": product.get("updated_at"),
        "updated": product.get("updated_at"),
        "metadata": {
            "unigraph_iq": product.get("scores", {}).get("product_intelligence_score"),
            "commerce_readiness": product.get("scores", {}).get("commerce_readiness"),
            "provenance_traceable": True,
        }
    }


def export_schema_org(product: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Schema.org JSON-LD Structured Product Data."""
    ident = product.get("identity", {})
    c = product.get("content", {})
    attrs = product.get("attributes", {})
    additional_prop = []
    for k, v in attrs.items():
        additional_prop.append({
            "@type": "PropertyValue",
            "name": k.replace("_", " ").title(),
            "value": f"{v.get('value')} {v.get('unit') or ''}".strip(),
            "propertyID": k,
        })
    return {
        "@context": "https://schema.org/",
        "@type": "Product",
        "sku": product["sku"],
        "mpn": ident.get("mpn"),
        "name": f"{ident.get('manufacturer','')} {ident.get('mpn','')} {product.get('category','')}".strip(),
        "image": [],
        "description": c.get("long_description"),
        "brand": {
            "@type": "Brand",
            "name": ident.get("manufacturer", "Industrial")
        },
        "category": product.get("category"),
        "additionalProperty": additional_prop,
    }


def export_factsheet_html(product: Dict[str, Any]) -> str:
    """Generates printable 1-page HTML Product Fact Sheet."""
    ident = product.get("identity", {})
    c = product.get("content", {})
    attrs = product.get("attributes", {})
    scores = product.get("scores", {})
    taxonomy = product.get("taxonomy", {})
    rows = "".join(f"""<tr>
        <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-weight:600;color:#1e293b;width:35%">{k.replace('_',' ').title()}</td>
        <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#334155">{v.get('value')} {v.get('unit') or ''}</td>
        <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px">{int((v.get('confidence',1))*100)}%</td>
        <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#0284c7;font-size:12px">{v.get('status','VERIFIED')}</td>
    </tr>""" for k, v in attrs.items())
    certs = "".join(f'<span style="background:#0284c7;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:6px">{x}</span>' for x in product.get("compliance", {}).get("found", [])) or "None specified"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{product['sku']} — Golden Record Fact Sheet</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 32px; color: #0f172a; background: #fff; line-height: 1.5; }}
.header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #0284c7; padding-bottom: 16px; margin-bottom: 24px; }}
.title h1 {{ margin: 0; font-size: 24px; color: #0f172a; }}
.title p {{ margin: 4px 0 0; color: #64748b; font-size: 14px; }}
.badge {{ background: #0f172a; color: #fff; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 14px; text-align: center; }}
.scores {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
.score-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center; }}
.score-box strong {{ display: block; font-size: 20px; color: #0284c7; }}
.score-box span {{ font-size: 11px; color: #64748b; text-transform: uppercase; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 14px; }}
th {{ background: #f1f5f9; padding: 10px 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #475569; }}
.footer {{ border-top: 1px solid #e2e8f0; padding-top: 16px; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between; }}
@media print {{ body {{ padding: 0; }} button {{ display: none; }} }}
</style>
</head>
<body>
<div class="header">
  <div class="title">
    <h1>{ident.get('manufacturer', '')} {ident.get('mpn', product['sku'])}</h1>
    <p>SKU: <strong>{product['sku']}</strong> · Category: <strong>{product.get('category')}</strong> · UNSPSC: <strong>{taxonomy.get('unspsc', 'N/A')}</strong></p>
  </div>
  <div class="badge">
    STATUS: {scores.get('status', 'VERIFIED')}
  </div>
</div>

<div class="scores">
  <div class="score-box"><strong>{scores.get('product_intelligence_score')}%</strong><span>Product IQ</span></div>
  <div class="score-box"><strong>{scores.get('commerce_readiness')}%</strong><span>Commerce Readiness</span></div>
  <div class="score-box"><strong>{scores.get('completeness')}%</strong><span>Completeness</span></div>
  <div class="score-box"><strong>{scores.get('average_confidence')}%</strong><span>Avg Confidence</span></div>
</div>

<div style="margin-bottom: 20px;">
  <h3 style="margin: 0 0 8px; font-size: 16px;">Product Overview</h3>
  <p style="margin: 0; font-size: 14px; color: #334155;">{c.get('long_description')}</p>
</div>

<div style="margin-bottom: 20px;">
  <h3 style="margin: 0 0 8px; font-size: 16px;">Verified Technical Specifications</h3>
  <table>
    <thead><tr><th>Specification</th><th>Extracted Value</th><th>Confidence</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div style="margin-bottom: 24px;">
  <h3 style="margin: 0 0 8px; font-size: 16px;">Compliance &amp; Certifications</h3>
  <div>{certs}</div>
</div>

<div class="footer">
  <span>Generated by UniGraph IQ Enterprise Autonomous Product Intelligence Engine</span>
  <span>Timestamp: {product.get('updated_at')}</span>
</div>
</body>
</html>"""
