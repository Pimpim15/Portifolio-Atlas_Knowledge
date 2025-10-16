<template>
  <main class="analytics">
    <header class="analytics__header">
      <div>
        <p class="analytics__kicker">Atlas Knowledge</p>
        <h1>Insights de conhecimento</h1>
        <p class="analytics__subtitle">
          Visualize documentos publicados, tags em alta e autores ativos para orientar o backlog.
        </p>
      </div>
      <div class="analytics__actions">
        <button class="btn btn-ghost" :disabled="isLoading" @click="refresh">
          {{ isLoading ? 'Atualizando...' : 'Atualizar' }}
        </button>
        <RouterLink class="btn btn-secondary" to="/">Voltar para a busca</RouterLink>
      </div>
    </header>

    <section v-if="error" class="analytics__error">
      <h2>Não foi possível carregar os insights</h2>
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="refresh">Tentar novamente</button>
    </section>

    <section v-else>
      <section v-if="isLoading" class="analytics__loading">
        <div v-for="skeleton in 6" :key="skeleton" class="analytics__skeleton"></div>
      </section>

      <section v-else-if="stats" class="analytics__content">
        <section class="metrics-grid">
          <article class="metric-card">
            <h3>Total de documentos</h3>
            <p class="metric-card__value">{{ stats.totals.documents }}</p>
            <span class="metric-card__hint">{{ todayCount }} adicionados nas últimas 24h</span>
          </article>
          <article class="metric-card">
            <h3>Versões publicadas</h3>
            <p class="metric-card__value">{{ stats.totals.versions }}</p>
            <span class="metric-card__hint">Atratividade de conteúdo</span>
          </article>
          <article class="metric-card">
            <h3>Tags únicas</h3>
            <p class="metric-card__value">{{ stats.totals.unique_tags }}</p>
            <span class="metric-card__hint">Média {{ stats.totals.avg_tags_per_document.toFixed(2) }} tags/doc</span>
          </article>
          <article class="metric-card">
            <h3>Autores ativos</h3>
            <p class="metric-card__value">{{ stats.totals.active_authors }}</p>
            <span class="metric-card__hint">{{ weeklyAverage }} docs/dia (média 7d)</span>
          </article>
        </section>

        <section class="chart-card">
          <header class="chart-card__header">
            <h2>Documentos por dia (últimos 30 dias)</h2>
            <div class="chart-card__labels">
              <span>{{ rangeLabels.start }}</span>
              <span>{{ rangeLabels.end }}</span>
            </div>
          </header>
          <svg :viewBox="`0 0 100 ${chartHeight}`" preserveAspectRatio="none" class="chart-card__sparkline">
            <polyline
              class="chart-card__sparkline-line"
              :points="sparklinePoints"
              fill="none"
              stroke="url(#sparklineGradient)"
              stroke-width="2.4"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
            <defs>
              <linearGradient id="sparklineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.9" />
                <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.2" />
              </linearGradient>
            </defs>
          </svg>
        </section>

        <section class="lists-grid">
          <article class="list-card">
            <h3>Tags em evidência</h3>
            <ul>
              <li v-for="tag in stats.top_tags" :key="tag.tag">
                <span>{{ tag.tag }}</span>
                <span class="list-card__badge">{{ tag.count }}</span>
              </li>
              <li v-if="!stats.top_tags.length" class="list-card__empty">Nenhuma tag registrada.</li>
            </ul>
          </article>
          <article class="list-card">
            <h3>Autores mais ativos</h3>
            <ul>
              <li v-for="author in stats.top_authors" :key="author.author_id ?? author.display_name">
                <span>{{ author.display_name }}</span>
                <span class="list-card__badge">{{ author.count }}</span>
              </li>
              <li v-if="!stats.top_authors.length" class="list-card__empty">Nenhum autor registrado.</li>
            </ul>
          </article>
        </section>

        <section class="recent-card">
          <header>
            <h3>Publicações recentes</h3>
          </header>
          <table>
            <thead>
              <tr>
                <th>Título</th>
                <th>Autor</th>
                <th>Tags</th>
                <th>Criado em</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="doc in stats.recent_documents" :key="doc.id">
                <td>{{ doc.title }}</td>
                <td>{{ doc.author }}</td>
                <td>
                  <span v-for="tag in doc.tags" :key="tag" class="recent-card__tag">{{ tag }}</span>
                  <span v-if="!doc.tags.length" class="recent-card__tag recent-card__tag--muted">-</span>
                </td>
                <td>{{ formatDateTime(doc.created_at) }}</td>
              </tr>
              <tr v-if="!stats.recent_documents.length">
                <td colspan="4" class="recent-card__empty">Nenhum documento recente encontrado.</td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import api from '../utils/api';

type DocumentStatsResponse = {
  totals: {
    documents: number;
    versions: number;
    unique_tags: number;
    active_authors: number;
    avg_tags_per_document: number;
  };
  top_tags: Array<{ tag: string; count: number }>;
  top_authors: Array<{ author_id: string | null; display_name: string; count: number }>;
  documents_by_day: Array<{ date: string; count: number }>;
  recent_documents: Array<{ id: string; title: string; created_at: string; tags: string[]; author: string }>;
};

const isLoading = ref(true);
const error = ref<string | null>(null);
const stats = ref<DocumentStatsResponse | null>(null);

const chartHeight = 80;

const sparklinePoints = computed(() => {
  if (!stats.value?.documents_by_day.length) {
    return '';
  }
  const data = stats.value.documents_by_day;
  const maxCount = Math.max(...data.map((point) => point.count), 1);
  const width = Math.max(data.length - 1, 1);
  return data
    .map((point, index) => {
      const x = (index / width) * 100;
      const y = chartHeight - (point.count / maxCount) * chartHeight;
      return `${x},${y}`;
    })
    .join(' ');
});

const todayCount = computed(() => stats.value?.documents_by_day.at(-1)?.count ?? 0);

const weeklyAverage = computed(() => {
  if (!stats.value) {
    return '0';
  }
  const lastSeven = stats.value.documents_by_day.slice(-7);
  const total = lastSeven.reduce((sum, point) => sum + point.count, 0);
  return (total / (lastSeven.length || 1)).toFixed(1);
});

const rangeLabels = computed(() => {
  if (!stats.value?.documents_by_day.length) {
    return { start: '-', end: '-' };
  }
  const format = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' });
  const first = new Date(`${stats.value.documents_by_day[0].date}T00:00:00`);
  const last = new Date(`${stats.value.documents_by_day.at(-1)?.date ?? ''}T00:00:00`);
  return {
    start: format.format(first),
    end: format.format(last),
  };
});

const formatDateTime = (iso: string) => {
  const formatter = new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
  return formatter.format(new Date(iso));
};

const loadStats = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    const { data } = await api.get<DocumentStatsResponse>('/docs/stats');
    stats.value = data;
  } catch (err) {
    const maybeResponse = err as { response?: { data?: { detail?: string } } };
    error.value = maybeResponse.response?.data?.detail ?? 'Tente novamente em instantes.';
  } finally {
    isLoading.value = false;
  }
};

const refresh = () => {
  if (!isLoading.value) {
    loadStats();
  }
};

onMounted(loadStats);
</script>

<style scoped>
.analytics {
  min-height: 100vh;
  padding: 3rem clamp(1.5rem, 5vw, 5rem) 4rem;
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
}

.analytics__header {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.analytics__kicker {
  letter-spacing: 0.18em;
  font-size: 0.75rem;
  text-transform: uppercase;
  color: rgba(148, 163, 184, 0.7);
  margin-bottom: 0.25rem;
}

.analytics__subtitle {
  margin-top: 0.75rem;
  max-width: 520px;
  color: rgba(226, 232, 240, 0.75);
}

.analytics__actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.analytics__error {
  padding: 2rem;
  border-radius: 20px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  background: rgba(127, 29, 29, 0.3);
  display: grid;
  gap: 1rem;
}

.analytics__loading {
  display: grid;
  gap: 1rem;
}

.analytics__skeleton {
  height: 120px;
  border-radius: 16px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.12), rgba(148, 163, 184, 0.28), rgba(148, 163, 184, 0.12));
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.metrics-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.metric-card {
  padding: 1.75rem;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.55);
  display: grid;
  gap: 0.75rem;
}

.metric-card__value {
  font-size: clamp(2rem, 5vw, 2.75rem);
  margin: 0;
  font-weight: 600;
}

.metric-card__hint {
  color: rgba(148, 163, 184, 0.85);
  font-size: 0.9rem;
}

.chart-card {
  padding: 2rem;
  border-radius: 20px;
  border: 1px solid rgba(56, 189, 248, 0.35);
  background: linear-gradient(145deg, rgba(30, 58, 138, 0.45), rgba(37, 99, 235, 0.32));
  display: grid;
  gap: 1.25rem;
}

.chart-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.chart-card__labels {
  display: flex;
  gap: 0.75rem;
  font-size: 0.9rem;
  color: rgba(226, 232, 240, 0.8);
}

.chart-card__sparkline {
  width: 100%;
  height: 160px;
}

.chart-card__sparkline-line {
  fill: none;
}

.lists-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.list-card {
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.5);
  padding: 1.75rem;
  display: grid;
  gap: 1.25rem;
}

.list-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.75rem;
}

.list-card li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.list-card__badge {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.85rem;
}

.list-card__empty {
  color: rgba(148, 163, 184, 0.8);
  font-style: italic;
}

.recent-card {
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.55);
  padding: 1.75rem;
  display: grid;
  gap: 1.25rem;
  overflow-x: auto;
}

.recent-card table {
  width: 100%;
  border-collapse: collapse;
}

.recent-card th,
.recent-card td {
  padding: 0.75rem;
  text-align: left;
  font-size: 0.95rem;
}

.recent-card thead {
  background: rgba(15, 23, 42, 0.65);
}

.recent-card__tag {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.65rem;
  margin-right: 0.35rem;
  margin-bottom: 0.35rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  color: rgba(226, 232, 240, 0.85);
  font-size: 0.85rem;
}

.recent-card__tag--muted {
  background: transparent;
  color: rgba(148, 163, 184, 0.6);
}

.recent-card__empty {
  text-align: center;
  padding: 1.5rem 0;
  color: rgba(148, 163, 184, 0.8);
}

@keyframes shimmer {
  0% {
    background-position-x: 0;
  }
  100% {
    background-position-x: -200%;
  }
}

@media (max-width: 768px) {
  .analytics {
    padding: 2.5rem 1.25rem 3rem;
  }

  .analytics__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .chart-card__labels {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
