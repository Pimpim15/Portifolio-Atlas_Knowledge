"""Coletores de métricas custom."""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter("atlas_request_total", "Total de requisições", ["method", "route", "status"])
REQUEST_LATENCY = Histogram("atlas_request_latency_seconds", "Latência das requisições", ["route"])
