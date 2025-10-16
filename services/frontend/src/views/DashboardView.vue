<template>
  <main class="dashboard">
    <header class="dashboard__header">
      <div>
        <p class="dashboard__kicker">Atlas Knowledge</p>
        <h1>Bem-vindo de volta, {{ displayName }}</h1>
        <p class="dashboard__subtitle">Centralize runbooks, políticas e conhecimento crítico em um único lugar.</p>
      </div>
      <div class="dashboard__actions">
        <button v-if="canManageDocs" class="btn btn-secondary" @click="openCreateModal">Novo documento</button>
        <RouterLink class="btn btn-ghost" to="/analytics">Insights</RouterLink>
        <button class="btn btn-ghost" @click="handleLogout">Sair</button>
      </div>
    </header>

    <section class="search-card">
  <form class="search-card__form" @submit.prevent="performSearch()">
        <div class="search-card__inputs">
          <input
            v-model="query"
            class="input"
            type="search"
            placeholder="Busque por runbooks, políticas, procedimentos..."
          />
          <input
            v-model="tagsFilter"
            class="input input--ghost"
            type="text"
            placeholder="Filtrar por tags (separe com vírgulas)"
          />
        </div>
        <button class="btn btn-primary" type="submit" :disabled="isLoading">
          {{ isLoading ? 'Buscando...' : 'Buscar' }}
        </button>
      </form>
      <p class="search-card__hint">Exemplos: "backup", "incident", "runbook"</p>
    </section>

    <section class="result-grid">
      <article v-for="doc in results" :key="doc.id" class="result-card" @click="openResultModal(doc)">
        <header>
          <h2>{{ doc.title }}</h2>
          <ul class="tag-list">
            <li v-for="tag in doc.tags" :key="tag">{{ tag }}</li>
          </ul>
        </header>
        <p>{{ doc.snippet }}</p>
        <div class="result-card__cta">
          <span>Visualizar detalhes</span>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 8.25L21 12l-3.75 3.75M21 12H3" />
          </svg>
        </div>
      </article>

      <p v-if="!results.length && !isLoading" class="empty-state">
        Ainda não há resultados. Faça uma busca para começar ou crie um novo documento.
      </p>
    </section>

    <ReindexPanel v-if="canManageDocs" />

    <Modal :show="resultsModalOpen" @close="resultsModalOpen = false">
      <template #title>
        {{ selectedDoc?.title || 'Resultados da busca' }}
      </template>
      <div v-if="selectedDoc" class="modal-content">
        <p class="modal-content__snippet">{{ selectedDoc.snippet }}</p>
        <ul class="tag-list">
          <li v-for="tag in selectedDoc.tags" :key="tag">{{ tag }}</li>
        </ul>
      </div>
      <p v-else class="modal-content__empty">Nenhum documento encontrado para os filtros informados.</p>
      <template #actions>
        <button class="btn btn-ghost" @click="resultsModalOpen = false">Fechar</button>
        <button
          v-if="selectedDoc && canManageDocs"
          class="btn btn-secondary"
          @click="handleEditSelected"
        >
          Editar
        </button>
        <button
          v-if="selectedDoc && canManageDocs"
          class="btn btn-danger"
          @click="handleDeleteSelected"
        >
          Excluir
        </button>
        <button
          v-if="selectedDoc"
          class="btn btn-primary"
          @click="goToDocument(selectedDoc.id)"
        >
          Abrir documento
        </button>
      </template>
    </Modal>

    <Modal :show="errorModalOpen" @close="errorModalOpen = false">
      <template #title>Algo não saiu como esperado</template>
      <p class="modal-error">{{ errorMessage }}</p>
      <template #actions>
        <button class="btn btn-primary" @click="errorModalOpen = false">Entendi</button>
      </template>
    </Modal>

    <Modal :show="createModalOpen" @close="closeCreateModal">
      <template #title>{{ formMode === 'edit' ? 'Editar documento' : 'Novo documento' }}</template>
      <form class="create-form" @submit.prevent="submitForm">
        <label>
          Título
          <input v-model="newDoc.title" class="input" placeholder="Ex.: Plano de resposta a incidentes" required />
        </label>
        <label>
          Tags
          <input v-model="newDoc.tags" class="input input--ghost" placeholder="infra, segurança" />
        </label>
        <label>
          Conteúdo
          <textarea v-model="newDoc.body" class="textarea" rows="8" placeholder="Descreva o procedimento..." required></textarea>
        </label>
        <div class="create-form__actions">
          <button type="button" class="btn btn-ghost" @click="closeCreateModal">Cancelar</button>
          <button type="submit" class="btn btn-primary" :disabled="isSubmitting">
            {{ isSubmitting ? 'Salvando...' : formMode === 'edit' ? 'Salvar alterações' : 'Salvar documento' }}
          </button>
        </div>
      </form>
    </Modal>

    <Modal :show="successModalOpen" @close="successModalOpen = false">
      <template #title>{{ successModalTitle }}</template>
      <p class="modal-success">{{ successMessage }}</p>
      <template #actions>
        <button class="btn btn-primary" @click="successModalOpen = false">Fechar</button>
      </template>
    </Modal>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import Modal from '../components/Modal.vue';
import ReindexPanel from '../components/ReindexPanel.vue';
import api from '../utils/api';
import { useAuthStore } from '../store/auth';

type SearchResult = {
  id: string;
  title: string;
  snippet: string;
  tags: string[];
};

type DocumentDetail = {
  id: string;
  title: string;
  body: string;
  tags: string[];
};

const router = useRouter();
const authStore = useAuthStore();

const query = ref('');
const tagsFilter = ref('');
const results = ref<SearchResult[]>([]);
const isLoading = ref(false);
const isSubmitting = ref(false);
const resultsModalOpen = ref(false);
const errorModalOpen = ref(false);
const createModalOpen = ref(false);
const successModalOpen = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const successModalTitle = ref('Sucesso');
const selectedDoc = ref<SearchResult | null>(null);
const formMode = ref<'create' | 'edit'>('create');
const editingDocId = ref<string | null>(null);

const newDoc = reactive({
  title: '',
  body: '',
  tags: '',
});

const displayName = computed(() => authStore.user?.email?.split('@')[0] ?? 'Explorer');
const canManageDocs = computed(() => authStore.user?.roles?.some((role) => ['admin', 'editor'].includes(role)) ?? false);

const resetForm = () => {
  newDoc.title = '';
  newDoc.body = '';
  newDoc.tags = '';
};

const performSearch = async () => {
  isLoading.value = true;
  try {
    const params: Record<string, string> = {};
    if (query.value.trim()) params.q = query.value.trim();
    if (tagsFilter.value.trim()) params.tags = tagsFilter.value.trim();
    const { data } = await api.get<{ results: SearchResult[] }>('/search', { params });
    results.value = data.results;
    selectedDoc.value = null;
    resultsModalOpen.value = false;
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    errorMessage.value = detail ?? 'Não foi possível executar a busca. Tente novamente em instantes.';
    errorModalOpen.value = true;
  } finally {
    isLoading.value = false;
  }
};

const openResultModal = (doc: SearchResult) => {
  selectedDoc.value = doc;
  resultsModalOpen.value = true;
};

const goToDocument = (id: string) => {
  resultsModalOpen.value = false;
  router.push({ name: 'document-detail', params: { id } });
};

const openCreateModal = () => {
  formMode.value = 'create';
  editingDocId.value = null;
  resetForm();
  createModalOpen.value = true;
};

const closeCreateModal = () => {
  createModalOpen.value = false;
  resetForm();
  formMode.value = 'create';
  editingDocId.value = null;
};

const startEdit = async (docId: string) => {
  try {
    const { data } = await api.get<DocumentDetail>(`/docs/${docId}`);
    formMode.value = 'edit';
    editingDocId.value = data.id;
    newDoc.title = data.title;
    newDoc.body = data.body;
    newDoc.tags = (data.tags ?? []).join(', ');
    resultsModalOpen.value = false;
    createModalOpen.value = true;
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    errorMessage.value = detail ?? 'Não foi possível carregar o documento para edição.';
    errorModalOpen.value = true;
  }
};

const submitForm = async () => {
  if (!newDoc.title.trim() || !newDoc.body.trim()) {
    errorMessage.value = 'Título e conteúdo são obrigatórios.';
    errorModalOpen.value = true;
    return;
  }

  isSubmitting.value = true;
  try {
    const payload = {
      title: newDoc.title.trim(),
      body: newDoc.body.trim(),
      tags: newDoc.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
    };
    if (formMode.value === 'edit' && editingDocId.value) {
      const { data } = await api.put(`/docs/${editingDocId.value}`, payload);
      successModalTitle.value = 'Documento atualizado';
      successMessage.value = `"${data.title}" foi atualizado com sucesso.`;
    } else {
      const { data } = await api.post('/docs', payload);
      successModalTitle.value = 'Documento criado com sucesso';
      successMessage.value = `"${data.title}" agora faz parte do seu catálogo.`;
    }
    successModalOpen.value = true;
    closeCreateModal();
    await performSearch();
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    errorMessage.value = detail ?? 'Não foi possível salvar o documento. Verifique os dados e tente novamente.';
    errorModalOpen.value = true;
  } finally {
    isSubmitting.value = false;
  }
};

const handleEditSelected = async () => {
  if (!selectedDoc.value) return;
  await startEdit(selectedDoc.value.id);
};

const handleDeleteSelected = async () => {
  if (!selectedDoc.value) return;
  const confirmation = window.confirm('Tem certeza de que deseja excluir este documento?');
  if (!confirmation) {
    return;
  }
  try {
    await api.delete(`/docs/${selectedDoc.value.id}`);
    successModalTitle.value = 'Documento removido';
    successMessage.value = 'Documento removido com sucesso.';
    successModalOpen.value = true;
    resultsModalOpen.value = false;
    selectedDoc.value = null;
    await performSearch();
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    errorMessage.value = detail ?? 'Não foi possível excluir o documento. Tente novamente.';
    errorModalOpen.value = true;
  }
};

const handleLogout = () => {
  authStore.logout();
  router.push({ name: 'login' });
};

watch(query, (newValue, oldValue) => {
  if (oldValue && newValue === '') {
    performSearch();
  }
});

watch(tagsFilter, (newValue, oldValue) => {
  if (oldValue && newValue === '') {
    performSearch();
  }
});

onMounted(async () => {
  if (!authStore.user) {
    try {
      await authStore.fetchCurrentUser();
    } catch {
      return;
    }
  }
  await performSearch();
});
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  padding: 3rem clamp(1.5rem, 5vw, 5rem) 4rem;
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
}

.dashboard__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
}

.dashboard__kicker {
  letter-spacing: 0.2em;
  font-size: 0.75rem;
  text-transform: uppercase;
  color: rgba(148, 163, 184, 0.8);
  margin-bottom: 0.5rem;
}

.dashboard__subtitle {
  margin-top: 0.75rem;
  max-width: 520px;
  color: rgba(226, 232, 240, 0.75);
}

.dashboard__actions {
  display: flex;
  gap: 0.75rem;
}

.search-card {
  background: linear-gradient(135deg, rgba(30, 64, 175, 0.45), rgba(59, 130, 246, 0.35));
  border-radius: 20px;
  padding: 2rem clamp(1.5rem, 4vw, 3rem);
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.35);
}

.search-card__form {
  display: grid;
  gap: 1rem;
}

.search-card__inputs {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.search-card__hint {
  margin-top: 1rem;
  font-size: 0.85rem;
  color: rgba(226, 232, 240, 0.75);
}

.result-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.result-card {
  background: rgba(15, 23, 42, 0.7);
  border-radius: 18px;
  padding: 1.75rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  transition: transform 0.2s ease, border 0.2s ease, box-shadow 0.2s ease;
  display: grid;
  gap: 1.15rem;
  cursor: pointer;
}

.result-card:hover {
  transform: translateY(-4px);
  border-color: rgba(56, 189, 248, 0.6);
  box-shadow: 0 18px 36px rgba(8, 15, 35, 0.35);
}

.result-card h2 {
  margin: 0;
  font-size: 1.25rem;
  line-height: 1.4;
}

.result-card p {
  margin: 0;
  color: rgba(226, 232, 240, 0.78);
}

.result-card__cta {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: #38bdf8;
  font-weight: 600;
}

.result-card__cta svg {
  width: 18px;
  height: 18px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0;
  margin: 0;
  list-style: none;
}

.tag-list li {
  background: rgba(148, 163, 184, 0.15);
  color: rgba(226, 232, 240, 0.85);
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  letter-spacing: 0.02em;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 3rem;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 16px;
  border: 1px dashed rgba(148, 163, 184, 0.35);
  color: rgba(226, 232, 240, 0.75);
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 0.75rem 1.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
  font-size: 0.95rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, #38bdf8, #14b8a6);
  color: #0f172a;
  box-shadow: 0 10px 25px rgba(20, 184, 166, 0.35);
}

.btn-primary:hover:enabled {
  transform: translateY(-2px);
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.2);
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.35);
}

.btn-ghost {
  background: transparent;
  color: rgba(226, 232, 240, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.btn-ghost:hover {
  border-color: rgba(148, 163, 184, 0.45);
}

.input,
.textarea {
  width: 100%;
  border: none;
  border-radius: 14px;
  padding: 0.85rem 1rem;
  background: rgba(15, 23, 42, 0.6);
  color: #f8fafc;
  font-size: 0.95rem;
  border: 1px solid transparent;
  transition: border 0.2s ease, box-shadow 0.2s ease;
}

.input:focus,
.textarea:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.6);
  box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.15);
}

.input--ghost {
  background: rgba(148, 163, 184, 0.12);
}

.textarea {
  resize: vertical;
  min-height: 180px;
}

.modal-content {
  display: grid;
  gap: 1rem;
}

.modal-content__snippet {
  color: rgba(226, 232, 240, 0.85);
  line-height: 1.6;
}

.modal-content__empty {
  color: rgba(226, 232, 240, 0.75);
}

.modal-error {
  color: #fda4af;
  line-height: 1.6;
}

.modal-success {
  color: #bbf7d0;
  line-height: 1.6;
}

.create-form {
  display: grid;
  gap: 1.25rem;
}

.create-form label {
  display: grid;
  gap: 0.75rem;
  font-weight: 600;
}

.create-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

@media (max-width: 640px) {
  .dashboard {
    padding: 2rem 1.25rem 3rem;
  }

  .dashboard__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .btn {
    width: 100%;
  }

  .result-card {
    padding: 1.5rem;
  }
}
</style>
