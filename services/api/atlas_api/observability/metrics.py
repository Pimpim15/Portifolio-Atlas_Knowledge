"""Coletores de métricas custom."""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter("atlas_request_total", "Total de requisições", ["method", "route", "status"])
REQUEST_LATENCY = Histogram("atlas_request_latency_seconds", "Latência das requisições", ["route"])

REINDEX_JOB_COUNT = Counter(
	"atlas_reindex_jobs_total",
	"Total de execuções do reindex",
	["status"],
)
REINDEX_JOB_LATENCY = Histogram(
	"atlas_reindex_job_latency_seconds",
	"Tempo gasto para preparar jobs de reindex",
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
WORKER_PROCESSING_LATENCY = Histogram(
	"atlas_worker_processing_latency_seconds",
	"Latência para processar mensagens por ação no worker",
	["action"],
)
WORKER_PROCESSING_ERRORS = Counter(
	"atlas_worker_processing_errors_total",
	"Total de erros ao processar mensagens pelo worker",
	["action"],
)
