# Local infrastructure

Root docker-compose.yml owns the local PostgreSQL, one-shot migration, backend and frontend services. Named storage survives normal stop/down. Images use supported major-version tags; production must pin reviewed digests and provision separate migration/runtime roles, backups, TLS and private object storage. No cloud resources are provisioned in Phase 1.
