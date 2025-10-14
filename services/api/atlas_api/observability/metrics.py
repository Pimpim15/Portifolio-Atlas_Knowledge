"""Coletores de métricas custom."""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter("atlas_request_total", "Total de requisições", ["method", "route", "status"])
REQUEST_LATENCY = Histogram("atlas_request_latency_seconds", "Latência das requisições", ["route"])

REINDEX_JOB_COUNT = Counter(
	"atlas_reindex_jobs_total",
	"Total de execuções do reindex",
	["status"],
)
REINDEX_DOCUMENT_ENQUEUED = Counter(
	"atlas_reindex_documents_enqueued_total",
	"Total de documentos enfileirados em reindex",
)
WORKER_ACTION_COUNT = Counter(
	"atlas_worker_actions_total",
	"Total de ações processadas pelo worker",
	["action"],
)
