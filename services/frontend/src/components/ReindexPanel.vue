<template>
  <section class="reindex">
    <header class="reindex__header">
      <div>
        <p class="reindex__kicker">Reindexação</p>
        <h2>Sincronize o catálogo com o OpenSearch</h2>
        <p class="reindex__description">
          Execute uma reindexação completa quando houver inconsistências entre o banco relacional e o cluster de busca.
          Acompanhe o progresso em tempo real e consulte erros para agir rapidamente.
        </p>
      </div>
      <div class="reindex__actions">
        <button class="btn btn-ghost" type="button" :disabled="isLoadingJobs" @click="fetchJobs(true)">
          {{ isLoadingJobs ? 'Atualizando...' : 'Atualizar' }}
        </button>
        <button class="btn btn-secondary" type="button" :disabled="isTriggering" @click="triggerReindex">
          {{ isTriggering ? 'Disparando...' : 'Disparar reindexação' }}
        </button>
      </div>
    </header>

    <section class="reindex__summary" aria-label="Resumo dos jobs de reindexação">
      <div class="reindex__summary-card">
        <span class="reindex__summary-label">Jobs nas últimas execuções</span>
        <strong class="reindex__summary-value">{{ summary.total }}</strong>
      </div>
      <div class="reindex__summary-card">
        <span class="reindex__summary-label">Em andamento</span>
        <strong class="reindex__summary-value status--running">{{ summary.running }}</strong>
      </div>
      <div class="reindex__summary-card">
        <span class="reindex__summary-label">Concluídos</span>
        <strong class="reindex__summary-value status--success">{{ summary.success }}</strong>
      </div>
      <div class="reindex__summary-card">
        <span class="reindex__summary-label">Falhas</span>
        <strong class="reindex__summary-value status--failed">{{ summary.failed }}</strong>
      </div>
      <div class="reindex__summary-card" v-if="summary.lastRun">
        <span class="reindex__summary-label">Última execução</span>
        <strong class="reindex__summary-value">{{ summary.lastRun }}</strong>
      </div>
    </section>

    <Transition name="fade">
      <div v-if="toast" class="reindex__toast" :class="`reindex__toast--${toast.kind}`">
        {{ toast.message }}
      </div>
    </Transition>

    <div class="reindex__content" role="log" aria-live="polite">
      <p v-if="!jobs.length && !isLoadingJobs" class="reindex__empty">
        Nenhum job encontrado ainda. Dispare uma reindexação para popular o histórico.
      </p>
      <ul v-else class="reindex__list">
        <li v-for="job in jobs" :key="job.id" class="reindex__item">
          <div class="reindex__item-header">
            <div>
              <h3>Job {{ formatId(job.id) }}</h3>
              <p class="reindex__item-subtitle">
                Criado em {{ formatDate(job.created_at) }} · Atualizado em {{ formatDate(job.updated_at) }}
              </p>
            </div>
            <span class="status" :class="statusClass(job.status)">{{ statusLabel(job.status) }}</span>
          </div>
          <dl class="reindex__stats">
            <div>
              <dt>Total</dt>
              <dd>{{ job.total_documents ?? '—' }}</dd>
            </div>
            <div>
              <dt>Processados</dt>
              <dd>{{ job.processed_documents }}</dd>
            </div>
            <div>
              <dt>Pendentes</dt>
              <dd>{{ job.pending_items }}</dd>
            </div>
            <div>
              <dt>Em andamento</dt>
              <dd>{{ job.running_items }}</dd>
            </div>
            <div>
              <dt>Completos</dt>
              <dd>{{ job.success_items }}</dd>
            </div>
            <div>
              <dt>Falhas</dt>
              <dd class="reindex__stat-error">{{ job.failed_items }}</dd>
            </div>
          </dl>
          <div v-if="job.error_message" class="reindex__error">
            <strong>Último erro:</strong>
            <span>{{ job.error_message }}</span>
          </div>
          <footer class="reindex__item-actions">
            <button class="btn btn-ghost" type="button" @click="openJob(job)">
              Ver itens
            </button>
          </footer>
        </li>
      </ul>
    </div>

    <Modal :show="itemsModalOpen" @close="closeItemsModal">
      <template #title>
        Itens do job {{ currentJob ? formatId(currentJob.id) : '' }}
      </template>
      <div class="items">
        <p v-if="itemsError" class="items__error">{{ itemsError }}</p>
        <p v-else-if="!jobItems.length && isLoadingItems" class="items__loading">Carregando itens...</p>
        <p v-else-if="!jobItems.length" class="items__empty">Nenhum item encontrado para este job.</p>
        <ul v-else class="items__list">
          <li v-for="item in jobItems" :key="item.id" class="items__entry">
            <header>
              <h4>Documento {{ formatId(item.document_id) }}</h4>
              <span class="status" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span>
            </header>
            <p class="items__meta">Versão {{ item.version }} · Atualizado em {{ formatDate(item.updated_at) }}</p>
            <p v-if="item.error_message" class="items__error-message">{{ item.error_message }}</p>
          </li>
        </ul>
        <div v-if="itemsHasMore" class="items__load-more">
          <button class="btn btn-secondary" type="button" :disabled="isLoadingItems" @click="loadMoreItems">
            {{ isLoadingItems ? 'Carregando...' : 'Carregar mais' }}
          </button>
        </div>
      </div>
      <template #actions>
        <button class="btn btn-primary" type="button" @click="closeItemsModal">Fechar</button>
      </template>
    </Modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import Modal from './Modal.vue';
import api from '../utils/api';

type ReindexJobStatus = 'pending' | 'running' | 'success' | 'failed';

type ReindexJobSummary = {
  id: string;
  status: ReindexJobStatus;
  total_documents: number | null;
  processed_documents: number;
  created_at: string;
  updated_at: string;
  pending_items: number;
  running_items: number;
  success_items: number;
  failed_items: number;
  error_message: string | null;
};

type ReindexJobItem = {
  id: string;
  job_id: string;
  document_id: string;
  version: number;
  status: ReindexJobStatus;
  created_at: string;
  updated_at: string;
  error_message: string | null;
};

type ReindexJobItemsResponse = {
  items: ReindexJobItem[];
  next_cursor: string | null;
};

type ToastState = {
  kind: 'success' | 'error';
  message: string;
};

const jobs = ref<ReindexJobSummary[]>([]);
const isLoadingJobs = ref(false);
const isTriggering = ref(false);
const toast = ref<ToastState | null>(null);
const itemsModalOpen = ref(false);
const jobItems = ref<ReindexJobItem[]>([]);
const itemsCursor = ref<string | null>(null);
const itemsHasMore = ref(false);
const isLoadingItems = ref(false);
const itemsError = ref('');
const currentJob = ref<ReindexJobSummary | null>(null);

const summary = computed(() => {
  const total = jobs.value.length;
  const running = jobs.value.filter((job) => job.status === 'running').length;
  const failed = jobs.value.filter((job) => job.status === 'failed').length;
  const success = jobs.value.filter((job) => job.status === 'success').length;
  const lastJob = jobs.value[0];
  const lastRun = lastJob ? formatDate(lastJob.created_at) : null;
  return {
    total,
    running,
    failed,
    success,
    lastRun,
  };
});

let refreshTimer: number | undefined;

const statusLabel = (status: ReindexJobStatus) => {
  switch (status) {
    case 'pending':
      return 'Pendente';
    case 'running':
      return 'Em andamento';
    case 'success':
      return 'Concluído';
    case 'failed':
      return 'Falhou';
    default:
      return status;
  }
};

const statusClass = (status: ReindexJobStatus) => {
  return {
    pending: 'status--pending',
    running: 'status--running',
    success: 'status--success',
    failed: 'status--failed',
  }[status] ?? 'status--pending';
};

const formatId = (id: string) => `${id.slice(0, 8)}…${id.slice(-4)}`;
const formatDate = (iso: string) => new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
}).format(new Date(iso));

const setToast = (kind: ToastState['kind'], message: string) => {
  toast.value = { kind, message };
  window.setTimeout(() => {
    if (toast.value?.message === message) {
      toast.value = null;
    }
  }, 5000);
};

const fetchJobs = async (force = false) => {
  if (isLoadingJobs.value && !force) return;
  isLoadingJobs.value = true;
  try {
    const { data } = await api.get<ReindexJobSummary[]>('/docs/reindex', {
      params: { limit: 10, offset: 0 },
    });
    jobs.value = data;
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    setToast('error', detail ?? 'Não foi possível carregar os jobs de reindex.');
  } finally {
    isLoadingJobs.value = false;
  }
};

const triggerReindex = async () => {
  if (isTriggering.value) return;
  const confirmation = window.confirm(
    'Deseja realmente disparar uma reindexação completa? Isso pode gerar carga no OpenSearch.',
  );
  if (!confirmation) return;

  isTriggering.value = true;
  try {
    const { data } = await api.post<ReindexJobSummary>('/docs/reindex');
    setToast('success', 'Reindexação disparada com sucesso.');
    jobs.value = [data, ...jobs.value].slice(0, 10);
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    setToast('error', detail ?? 'Não foi possível disparar a reindexação.');
  } finally {
    isTriggering.value = false;
  }
};

const openJob = async (job: ReindexJobSummary) => {
  currentJob.value = job;
  jobItems.value = [];
  itemsCursor.value = null;
  itemsHasMore.value = false;
  itemsError.value = '';
  itemsModalOpen.value = true;
  await loadMoreItems();
};

const loadMoreItems = async () => {
  if (!currentJob.value) return;
  isLoadingItems.value = true;
  try {
    const params: Record<string, string | number> = { limit: 15 };
    if (itemsCursor.value) params.cursor = itemsCursor.value;
    const { data } = await api.get<ReindexJobItemsResponse>(
      `/docs/reindex/${currentJob.value.id}/items`,
      { params },
    );
    jobItems.value = [...jobItems.value, ...data.items];
    itemsCursor.value = data.next_cursor;
    itemsHasMore.value = Boolean(data.next_cursor);
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    itemsError.value = detail ?? 'Não foi possível carregar os itens deste job.';
  } finally {
    isLoadingItems.value = false;
  }
};

const closeItemsModal = () => {
  itemsModalOpen.value = false;
  currentJob.value = null;
  jobItems.value = [];
  itemsCursor.value = null;
  itemsHasMore.value = false;
  itemsError.value = '';
  fetchJobs(true);
};

onMounted(async () => {
  await fetchJobs(true);
  refreshTimer = window.setInterval(() => fetchJobs(), 15000);
});

onBeforeUnmount(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
  }
});
</script>

<style scoped>
.reindex {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 20px;
  padding: clamp(1.5rem, 3vw, 2.5rem);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  box-shadow: 0 16px 40px rgba(8, 15, 35, 0.35);
}

.reindex__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
}

.reindex__kicker {
  letter-spacing: 0.2em;
  text-transform: uppercase;
  font-size: 0.75rem;
  color: rgba(148, 163, 184, 0.8);
  margin-bottom: 0.5rem;
}

.reindex__description {
  margin-top: 0.75rem;
  max-width: 600px;
  color: rgba(226, 232, 240, 0.75);
}

.reindex__actions {
  display: flex;
  gap: 0.75rem;
}

.reindex__content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.reindex__summary {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.reindex__summary-card {
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 16px;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.reindex__summary-label {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(148, 163, 184, 0.75);
}

.reindex__summary-value {
  font-size: 1.45rem;
  font-weight: 700;
}

.reindex__empty {
  padding: 1rem;
  border: 1px dashed rgba(148, 163, 184, 0.35);
  border-radius: 12px;
  text-align: center;
  color: rgba(148, 163, 184, 0.85);
}

.reindex__list {
  display: grid;
  gap: 1rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.reindex__item {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.reindex__item-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: center;
}

.reindex__item-subtitle {
  color: rgba(148, 163, 184, 0.75);
  font-size: 0.9rem;
}

.reindex__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem 1rem;
}

.reindex__stats dt {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(148, 163, 184, 0.8);
}

.reindex__stats dd {
  margin: 0.25rem 0 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.reindex__stat-error {
  color: #fda4af;
}

.reindex__error {
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
}

.reindex__item-actions {
  display: flex;
  justify-content: flex-end;
}

.status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.status--pending {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}

.status--running {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}

.status--success {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}

.status--failed {
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
}

.reindex__toast {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 500;
}

.reindex__toast--success {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.4);
  color: #bbf7d0;
}

.reindex__toast--error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
}

.items {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.items__list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.items__entry {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  padding: 1rem;
  background: rgba(30, 41, 59, 0.55);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.items__entry header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.items__meta {
  color: rgba(148, 163, 184, 0.75);
  font-size: 0.85rem;
}

.items__error-message {
  color: #fecaca;
  font-size: 0.9rem;
}

.items__error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
  padding: 0.75rem 1rem;
  border-radius: 12px;
}

.items__load-more {
  display: flex;
  justify-content: center;
}

.items__loading,
.items__empty {
  text-align: center;
  color: rgba(148, 163, 184, 0.85);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .reindex__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .reindex__actions .btn {
    flex: 1;
  }
}
</style>
