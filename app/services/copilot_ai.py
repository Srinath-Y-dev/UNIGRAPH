from __future__ import annotations
import json
import os
import re
import requests
from typing import Dict, Any, List, Optional

SYSTEM_PROMPT = """You are the AI Catalog Intelligence Copilot for UniGraph IQ Enterprise 2.0.

### About UniGraph IQ Enterprise 2.0:
UniGraph IQ Enterprise is an autonomous, traceable product intelligence platform designed for industrial commerce, technical catalogs, and multi-channel PIM syndication.

Key Capabilities & Architecture:
1. Multi-Source Ingestion & Enrichment:
   - Ingests raw technical specifications, datasheets, PDFs, text, CSVs, and XLSX spreadsheets.
   - Deterministic extraction and metric/imperial unit normalization (Torque, Pressure, Voltage, Power, Temperature, Flow Rate, Enclosures).
   - Standard classification mapping to UNSPSC and ETIM-8.0 industry taxonomies.

2. Source-Authority Governance & QA Guardian:
   - 7-tier weighted authority voting: Manufacturer Datasheet (1.0) > Website (0.9) > Certified Database (0.85) > Distributor (0.7) > General Catalog (0.6) > User Input (0.5) > Steward Overrides (Authoritative).
   - QA Guardian automatically flags conflicting values across sources for human-in-the-loop review.
   - Data Stewards can perform in-line attribute overrides with real-time score recalculation and full audit trails.

3. Golden Record Publish Gate:
   - Verifies completeness threshold (>=70%), confidence threshold (>=75%), and ensures 0 unresolved critical attribute conflicts.
   - Assigns readiness statuses: READY_TO_PUBLISH, REVIEW_REQUIRED, or INSUFFICIENT_DATA.

4. Multi-Channel Syndication Hub:
   - Master Golden Record JSON with full provenance and confidence metrics.
   - Shopify CSV with formatted tags, HTML spec tables, and variants.
   - Akeneo / CX1 PIM JSON with family definitions and localized attribute scopes.
   - Schema.org / JSON-LD for B2B search engine optimization.
   - Printable 1-Page PDF/HTML Factsheets with scorecard badges.

5. Visual Graph & Comparison Matrix:
   - Interactive force-directed knowledge graph (physics simulation linking SKUs, manufacturers, categories, specs, and certifications).
   - Cross-reference comparison matrix with automated MATCH vs VARIANCE attribute classification.

6. Enterprise Observability & Security:
   - Role-Based Access Control (Admin, Product Manager, Data Steward, Compliance, Viewer, Integration).
   - Prometheus metrics endpoint (/metrics), health checks (/health), and audited event logging.

### Your Instructions:
- Answer user questions accurately, professionally, and concisely using the provided real-time Catalog Context and RAG Evidence.
- If the user asks about the UniGraph IQ project, architecture, features, workflows, or APIs, provide a detailed and helpful explanation.
- If the user asks about products in the catalog (e.g. status, conflicts, specs, manufacturers, categories, or readiness), reference the relevant SKUs and data from the catalog context.
- Format responses using clean, readable markdown (bold headers, bullet points, and code formatting where appropriate).
- Never hallucinate unsupported product specifications. Rely on the catalog records and indexed evidence provided.
"""

def generate_copilot_response(
    question: str,
    products: List[Dict[str, Any]],
    evidence_snippets: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generates an intelligent copilot answer using LLM when available, with deterministic fallback."""
    base_url = os.getenv("AI_BASE_URL", "").strip()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "gemini-1.5-flash").strip()

    # Prepare catalog summary context
    total_count = len(products)
    ready_count = sum(1 for p in products if p.get('status') == 'READY_TO_PUBLISH')
    review_count = sum(1 for p in products if p.get('status') == 'REVIEW_REQUIRED')
    conflict_count = sum(1 for p in products if p.get('conflict_count', 0) > 0)
    
    categories = sorted(list({p.get('category') for p in products if p.get('category')}))
    manufacturers = sorted(list({p.get('manufacturer') for p in products if p.get('manufacturer')}))

    # Identify matching products for context
    q_lower = question.lower()
    relevant_products = []
    for p in products:
        sku = str(p.get('sku', '')).lower()
        mpn = str(p.get('mpn', '')).lower()
        mfg = str(p.get('manufacturer', '')).lower()
        cat = str(p.get('category', '')).lower()
        if sku in q_lower or (mpn and mpn in q_lower) or (mfg and mfg in q_lower) or (cat and cat in q_lower):
            relevant_products.append(p)
    
    if not relevant_products and products:
        relevant_products = products[:8]

    # Try LLM if configured
    if base_url and api_key and model:
        catalog_context = {
            "catalog_summary": {
                "total_products": total_count,
                "ready_to_publish": ready_count,
                "review_required": review_count,
                "products_with_conflicts": conflict_count,
                "available_categories": categories,
                "manufacturers": manufacturers,
            },
            "relevant_products_sample": [
                {
                    "sku": p.get("sku"),
                    "mpn": p.get("mpn"),
                    "manufacturer": p.get("manufacturer"),
                    "category": p.get("category"),
                    "status": p.get("status"),
                    "completeness": p.get("completeness"),
                    "intelligence_score": p.get("intelligence_score"),
                    "commerce_score": p.get("commerce_score"),
                    "conflict_count": p.get("conflict_count", 0),
                    "attributes": p.get("attributes", {}) if isinstance(p.get("attributes"), dict) else {}
                }
                for p in relevant_products[:10]
            ],
            "rag_evidence_excerpts": [
                {
                    "sku": e.get("sku"),
                    "source_name": e.get("source_name"),
                    "source_type": e.get("source_type"),
                    "snippet": e.get("snippet")
                    
                }
                for e in evidence_snippets[:6]
            ]
        }

        user_content = (
            f"User Question: {question}\n\n"
            f"Live Catalog Context:\n{json.dumps(catalog_context, ensure_ascii=False, indent=2)}"
        )

        try:
            endpoint = base_url.rstrip("/") + "/chat/completions"
            resp = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    "temperature": 0.2,
                },
                timeout=25
            )
            if resp.status_code == 200:
                data = resp.json()
                answer_text = data["choices"][0]["message"]["content"].strip()
                
                # Match mentioned SKUs in the answer for quick action buttons
                mentioned_skus = []
                for p in products:
                    if p["sku"] in answer_text or p["sku"].lower() in q_lower:
                        if p not in mentioned_skus:
                            mentioned_skus.append(p)

                return {
                    "answer": answer_text,
                    "products": mentioned_skus[:10] if mentioned_skus else relevant_products[:5],
                    "evidence": evidence_snippets[:5] if ("evidence" in q_lower or "source" in q_lower or "datasheet" in q_lower) else []
                }
        except Exception:
            # Fall back to deterministic engine on connection/token error
            pass

    # Deterministic fallback
    return fallback_copilot_response(question, products, evidence_snippets)


def fallback_copilot_response(
    question: str,
    products: List[Dict[str, Any]],
    evidence_snippets: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Robust deterministic fallback handling project, architecture, and catalog queries."""
    q = question.lower().strip()
    
    # Project explanation / overview queries
    if any(k in q for k in ["what is unigraph", "about this project", "project details", "how does it work", "architecture", "what does this app do"]):
        return {
            "answer": (
                "**UniGraph IQ Enterprise 2.0** is an autonomous, traceable product intelligence platform designed for industrial commerce & PIM syndication.\n\n"
                "**Key Pillars & Features:**\n"
                "• **Deterministic Ingestion & Normalization:** Ingests datasheets, PDFs, and CSVs with metric/imperial normalization and UNSPSC / ETIM-8.0 classification.\n"
                "• **QA Guardian & 7-Tier Authority:** Weights sources (Datasheets > Websites > Catalogs > Overrides) and flags attribute discrepancies.\n"
                "• **Publish Policy Gate:** Automatically checks completeness (≥70%), confidence (≥75%), and unresolved conflicts before syndication.\n"
                "• **Multi-Channel Syndication Hub:** Export to Shopify CSV, Akeneo PIM JSON, Schema.org JSON-LD, and Printable Fact Sheets.\n"
                "• **Interactive Knowledge Graph:** Canvas physics simulation of product relationships and specs."
            ),
            "products": products[:5]
        }

    # Syndication formats query
    if any(k in q for k in ["syndicat", "export format", "shopify", "akeneo", "schema.org", "factsheet", "cx1"]):
        return {
            "answer": (
                "**UniGraph IQ Enterprise 2.0 Syndication Hub** supports multiple enterprise export standards:\n\n"
                "• **Master Golden JSON:** Complete attribute provenance, confidence scores, and raw evidence chunks.\n"
                "• **Shopify Product CSV:** Formatted handles, tags, HTML specification tables, and variant structures.\n"
                "• **Akeneo / CX1 PIM JSON:** Enterprise PIM payloads with family definitions and localized attribute scopes.\n"
                "• **Schema.org / JSON-LD:** Structured product data optimized for B2B e-commerce search engine discovery.\n"
                "• **Printable 1-Page Factsheet:** High-resolution HTML/PDF technical data sheet with scorecard badges."
            ),
            "products": products[:5]
        }

    # Governance & Roles query
    if any(k in q for k in ["role", "permission", "rbac", "access control"]):
        return {
            "answer": (
                "**UniGraph IQ Enterprise RBAC Roles & Permissions:**\n\n"
                "• **`admin`**: Full system administration, user management, API keys, and connector settings.\n"
                "• **`product_manager`**: Catalog enrichment, batch jobs, reviews, syndication exports, and audit logs.\n"
                "• **`data_steward`**: Catalog enrichment, attribute conflict overrides, and review approvals.\n"
                "• **`compliance`**: Certification audits and compliance review decisions.\n"
                "• **`viewer`**: Read-only access to catalog, comparisons, knowledge graphs, and copilot.\n"
                "• **`integration`**: Machine-to-machine API key ingestion and syndication access."
            ),
            "products": products[:5]
        }

    # Evidence / RAG query
    if any(x in q for x in ['evidence', 'source', 'datasheet', 'provenance']):
        return {
            'answer': f'Found {len(evidence_snippets)} source evidence excerpts indexed in the RAG repository matching your query.',
            'evidence': evidence_snippets[:10]
        }

    # Conflicts query
    if 'conflict' in q:
        hits = [p for p in products if p.get('conflict_count', 0) > 0]
        return {
            'answer': f'Identified **{len(hits)}** products with attribute conflicts needing Data Steward / QA Guardian review.',
            'products': hits[:20]
        }

    # Ready to publish query
    if 'ready' in q or 'publish' in q:
        hits = [p for p in products if p.get('status') == 'READY_TO_PUBLISH']
        return {
            'answer': f'**{len(hits)}** products have met all publish gate criteria (confidence ≥ 75%, completeness ≥ 70%, 0 conflicts) and are ready for multi-channel syndication.',
            'products': hits[:20]
        }

    # Incomplete products
    if any(k in q for k in ['missing', 'incomplete', 'low complete']):
        hits = sorted(products, key=lambda x: x.get('completeness', 0))
        return {
            'answer': 'Here are the catalog records with the lowest attribute completeness scores:',
            'products': hits[:20]
        }

    # Category matching
    for cat in ["contactor", "circuit breaker", "ball valve", "bearing", "motor", "pump", "sensor", "cable", "relay", "transformer", "flow meter", "actuator"]:
        if cat in q:
            hits = [p for p in products if cat in str(p.get('category', '')).lower()]
            if hits:
                return {
                    'answer': f'Found **{len(hits)}** products classified under category "**{cat.title()}**".',
                    'products': hits[:20]
                }

    # Direct SKU / MPN search
    for p in products:
        if p.get('sku', '').lower() in q or (p.get('mpn') and str(p['mpn']).lower() in q):
            return {
                'answer': (
                    f"**{p['sku']}** ({p.get('manufacturer','')} {p.get('mpn','')})\n"
                    f"• **Category:** {p.get('category','N/A')}\n"
                    f"• **Status:** {p.get('status','N/A')}\n"
                    f"• **Product IQ Score:** {p.get('intelligence_score',0)}%\n"
                    f"• **Commerce Score:** {p.get('commerce_score',0)}%\n"
                    f"• **Completeness:** {p.get('completeness',0)}%"
                ),
                'products': [p]
            }

    # Manufacturer query
    for p in products:
        m = (p.get('manufacturer') or '').lower()
        if m and len(m) > 2 and m in q:
            hits = [x for x in products if (x.get('manufacturer') or '').lower() == m]
            return {
                'answer': f'Found **{len(hits)}** products manufactured by **{p["manufacturer"]}** in the Golden Catalog.',
                'products': hits[:20]
            }

    # General default
    return {
        'answer': (
            f"The UniGraph IQ Golden Catalog currently contains **{len(products)} Golden Records**.\n\n"
            f"You can ask about:\n"
            f"• **Product specs & categories** (e.g. *\"Show all contactors\"* or *\"Schneider LC1D09BD specs\"*)\n"
            f"• **Governance & readiness** (e.g. *\"What is ready to publish?\"* or *\"Show attribute conflicts\"*)\n"
            f"• **Project & system details** (e.g. *\"How does the publish gate work?\"* or *\"What syndication formats are supported?\"*)"
        ),
        'products': products[:6]
    }
