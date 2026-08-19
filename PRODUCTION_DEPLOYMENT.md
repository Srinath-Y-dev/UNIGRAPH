# Production Deployment Checklist

## Security
- Set `AUTH_REQUIRED=true`.
- Set a unique high-entropy `ADMIN_PASSWORD` before first database initialization.
- Terminate TLS at a reverse proxy/load balancer.
- Put secrets in a secret manager, not `.env` in source control.
- Restrict CORS to approved origins.
- Rotate integration API keys.
- Integrate enterprise SSO/OIDC for organizational deployment.

## Data plane
- SQLite is appropriate for the included self-contained deployment and demos. For multi-instance/high-write deployments, replace the DB adapter with managed PostgreSQL.
- Use object storage for large assets and long-lived documents.
- Use a production vector index when evidence volume exceeds the lightweight included search layer.
- Use a dedicated graph database if graph traversals become a primary workload.

## AI plane
- Configure OCR/VLM for scanned PDFs and image-derived specifications.
- Pin model versions and prompts.
- Track model/version metadata in enrichment jobs.
- Keep generated/inferred facts distinguishable from extracted/verified facts.

## Reliability
- Run behind a process manager/load balancer.
- Add centralized logs and alerting around `/health` and `/metrics`.
- Back up catalog, audit, evidence, review, and connector metadata.
- Perform load, failover and disaster-recovery testing for the target SLA.

## Integrations
- Replace DEMO connectors with approved CX1/PIM/ERP/DAM endpoints.
- Add customer-specific taxonomy mappings and mandatory-attribute policies.
- Validate syndication payloads against destination schemas before publish.
