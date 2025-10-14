"""Coletores de métricas custom."""

from prometheus_client import Counter, Gauge, Histogram

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
REINDEX_JOB_STATUS = Gauge(
	"atlas_reindex_jobs_status",
	"Quantidade atual de jobs de reindex por status",
	["status"],
)
REINDEX_JOB_ITEMS_STATUS = Gauge(
	"atlas_reindex_job_items_status",
	"Quantidade atual de itens de reindex por status",
	["status"],
)
REINDEX_JOB_OLDEST_ACTIVE_AGE = Gauge(
	"atlas_reindex_job_oldest_active_seconds",
	"Idade (em segundos) do job de reindex mais antigo pendente ou em execução",
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
