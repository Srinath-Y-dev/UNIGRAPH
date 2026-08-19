# UniGraph IQ Enterprise 2.0

**Autonomous, traceable product intelligence for industrial commerce & PIM syndication.**

UniGraph IQ converts limited product inputs, raw technical specifications, and fragmented manufacturer documents into governed **Golden Product Records** with deterministic provenance, confidence scoring, QA Guardian conflict resolution, interactive knowledge graphs, side-by-side product comparison matrices, and multi-channel enterprise syndication.

---

## 🌟 Implemented Product Surfaces & Capabilities

### 1. Intelligence & Ingestion Engine
- **Autonomous Multi-Source Enrichment:** Single-product ingestion from SKU/MPN, raw text, and attachments (PDF, TXT, CSV, XLSX, and image asset metadata).
- **Expanded Industrial Taxonomy:** Automated classification for Contactors, Circuit Breakers, Ball Valves, Bearings, Electric Motors, Pumps, Sensors, Cables, Relays, Transformers, Flow Meters, and Pneumatic Actuators.
- **Industry Standard Coding:** Out-of-the-box mapping to **UNSPSC** and **ETIM-8.0** classification schemas.
- **Deep Unit Normalization:** Metric/Imperial conversions for Torque ($Nm, \text{ft-lb}$), Flow Rate ($GPM, LPM$), Pressure ($PSI, Bar, MPa$), Voltage ($AC/DC/kV$), Power ($kW, HP$), Temperature ($°C/°F$), and Enclosures ($NEMA, IP$).

### 2. Governance & QA Guardian
- **Source-Authority Weighting:** 7-tier authority voting (Manufacturer Datasheets $\to$ Websites $\to$ Certified Databases $\to$ Distributors $\to$ Catalogs $\to$ User Input $\to$ Steward Overrides).
- **QA Guardian Conflict Detection:** Multi-source discrepancy detection with clickable candidate selection and steward overrides.
- **In-Line Attribute Workbench:** Direct data steward overrides with real-time score recalculation and audit logging.
- **Publish-Policy Gate:** Automated compliance checking (minimum completeness, confidence thresholds, conflict blockers).

### 3. Visual Graph & Comparison Intelligence
- **Interactive Force-Directed Knowledge Graph:** HTML5 Canvas physics simulation visualizing relationships between Root SKUs, Manufacturers, Categories, Certifications, Specifications, and Similar Products.
- **Cross-Reference & Comparison Matrix:** Side-by-side diffing of 2–4 products with automated `MATCH` vs `VARIANCE` parameter classification and substitute recommendation scoring.

### 4. Multi-Channel Enterprise Syndication Hub
- **Master Golden Record JSON:** Complete attribute provenance, confidence, and source evidence chunks.
- **Shopify Product CSV:** Formatted handles, tags, HTML spec tables, and variant structures.
- **Akeneo / CX1 PIM JSON:** Standard enterprise PIM payloads with family categories and localized attribute scopes.
- **Schema.org / JSON-LD:** W3C-standard structured product data for B2B e-Commerce SEO.
- **Printable 1-Page Fact Sheet:** High-resolution HTML/PDF technical data sheet with scorecard badges.

### 5. Conversational Catalog Copilot & Operations
- **Natural Language Copilot:** Query by category, manufacturer, voltage/power parameters, publish readiness, and RAG evidence.
- **Faceted Catalog Search:** Multi-filter sidebar (Category, Status, Manufacturer, Completeness slider, Conflict checkbox).
- **Active Connector Simulator:** Real-time connection ping tests and webhook dispatch simulation.
- **Enterprise Security & Observability:** RBAC security (6 roles), machine API keys, Prometheus-style `/metrics`, and `/health` endpoints.

---

## 👥 Roles & Access Control

| Role | Permissions |
| :--- | :--- |
| `admin` | Full system control, user management, API keys, connector configuration |
| `product_manager` | Catalog enrichment, batch jobs, reviews, syndication exports, audit inspection |
| `data_steward` | Catalog enrichment, attribute conflict overrides, review decisions |
| `compliance` | Compliance review decisions, certification auditing |
| `viewer` | Read-only access to catalog, comparisons, graphs, and copilot |
| `integration` | Machine-to-machine API key ingestion and syndication access |

*When `AUTH_REQUIRED=false` (default for local development), the application runs in local-demo admin mode.*

Default bootstrap admin credentials:
- **Email:** `admin@unigraph.local`
- **Password:** value of `ADMIN_PASSWORD` (local fallback: `admin123!`)

---

## 🚀 Quickstart Guide

### Run on Windows
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py
python run.py
```
Open **`http://127.0.0.1:8000`** in your browser.

### Run on Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py
python run.py
```

### Docker Deployment
Copy `.env.example` to `.env`, set a strong `ADMIN_PASSWORD`, and launch:
```bash
docker compose up --build
```

---

## 📡 Enterprise API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/enrich` | Governed multi-source enrichment pipeline |
| `POST` | `/api/products/{sku}/attribute` | In-line steward override & live score recalculation |
| `POST` | `/api/compare` | Cross-reference 2–4 products and generate spec matrix |
| `GET` | `/api/products` | Retrieve Golden Record catalog |
| `GET` | `/api/products/{sku}` | Retrieve product details, scores, and publish gate |
| `GET` | `/api/products/{sku}/graph` | Knowledge graph nodes and edges |
| `GET` | `/api/catalog/analytics` | Category breakdown, completeness & quality analytics |
| `GET` | `/api/export/{sku}.json` | Master Golden Record export |
| `GET` | `/api/export/{sku}/syndication/{format}` | Syndication export (`shopify`, `akeneo`, `schema_org`, `factsheet`) |
| `GET` | `/api/export/catalog.csv` | Full master catalog CSV export |
| `POST` | `/api/copilot` | Natural language catalog query engine |
| `GET` | `/api/rag/search?q=...` | Full-text evidence retrieval |
| `POST` | `/api/bulk` | Bulk CSV enrichment job |
| `GET` | `/api/jobs` | Batch execution job history |
| `GET` | `/api/connectors` | Integration connector registry |
| `POST` | `/api/connectors/{name}/test` | Connector handshake ping test |
| `POST` | `/api/connectors/{name}/dispatch` | Webhook dispatch simulation |
| `POST` | `/api/reviews/{sku}` | Submit human-in-the-loop review decision |
| `GET` | `/api/audit` | Enterprise audit trail log |
| `POST` | `/api/auth/login` | Session login |
| `GET` | `/api/admin/users` | RBAC user management |
| `POST` | `/api/admin/api-keys` | Generate machine API keys |
| `GET` | `/health` | Health & latency check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | OpenAPI / Swagger interactive explorer |

---

## 🛡️ AI Trust Model & Provenance

The **deterministic extraction, normalization, and validation engine** remains authoritative. Optional LLM integrations are restricted to commercial copy generation and strictly instructed to rely solely on verified technical facts. Every extracted attribute retains its source document, extraction confidence, and authority score. Conflicting data points are surfaced to human stewards rather than silently hallucinated.

---

## 🧪 Automated Testing

Execute the comprehensive test suite:
```bash
python tests_smoke.py
```
Validates health checks, single/bulk enrichment, in-line attribute overrides, comparison matrices, syndication exports, and natural language copilot endpoints.
