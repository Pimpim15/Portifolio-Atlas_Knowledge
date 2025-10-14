<template>
  <section class="document" v-if="!isLoading && document">
    <header class="document__header">
      <RouterLink class="document__back" to="/">
        <span>◀</span>
        Voltar para a busca
      </RouterLink>
      <div class="document__title">
        <h1>{{ document.title }}</h1>
        <div class="document__meta">
          <span class="pill">Versão {{ document.version }}</span>
          <span v-if="document.updated_at" class="pill pill--ghost">
            Atualizado {{ formatRelative(document.updated_at) }}
          </span>
        </div>
      </div>
    </header>

    <ul class="tag-list">
      <li v-for="tag in document.tags" :key="tag">{{ tag }}</li>
    </ul>

    <article class="document__body" v-html="document.body"></article>
  </section>

  <section v-else class="document-loading">
    <div class="skeleton skeleton--title"></div>
    <div class="skeleton skeleton--line"></div>
    <div class="skeleton skeleton--line"></div>
    <div class="skeleton skeleton--line"></div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import api from '../utils/api';

interface DocumentDetail {
  id: string;
  title: string;
  body: string;
  version: number;
  tags: string[];
  updated_at: string | null;
}

const route = useRoute();
const document = ref<DocumentDetail | null>(null);
const isLoading = ref(true);

const formatRelative = (isoDate: string) => {
  const formatter = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' });
  const updated = new Date(isoDate);
  const now = new Date();
  const diffMs = updated.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  return formatter.format(diffDays, 'day');
};

const loadDocument = async () => {
  isLoading.value = true;
  try {
    const { data } = await api.get(`/docs/${route.params.id}`);
    document.value = data;
  } finally {
    isLoading.value = false;
  }
};

onMounted(loadDocument);
</script>

<style scoped>
.document {
  max-width: 840px;
  margin: 0 auto;
  padding: 3.5rem 1.5rem 4.5rem;
  display: grid;
  gap: 1.75rem;
}

.document__header {
  display: grid;
  gap: 1.5rem;
}

.document__back {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: #38bdf8;
  text-decoration: none;
}

.document__title h1 {
  margin: 0;
  font-size: clamp(2rem, 3vw, 2.8rem);
}

.document__meta {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.pill {
  background: rgba(56, 189, 248, 0.18);
  color: #38bdf8;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  font-size: 0.85rem;
}

.pill--ghost {
  background: rgba(148, 163, 184, 0.18);
  color: rgba(226, 232, 240, 0.8);
}

.tag-list {
  display: flex;
  gap: 0.5rem;
  padding: 0;
  margin: 0;
  list-style: none;
}

.tag-list li {
  background: rgba(148, 163, 184, 0.18);
  color: rgba(226, 232, 240, 0.85);
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  font-size: 0.8rem;
  letter-spacing: 0.03em;
}

.document__body {
  background: rgba(15, 23, 42, 0.55);
  border-radius: 20px;
  padding: clamp(1.75rem, 4vw, 2.75rem);
  border: 1px solid rgba(148, 163, 184, 0.25);
  line-height: 1.7;
  color: rgba(226, 232, 240, 0.92);
}

.document__body :deep(h2) {
  margin-top: 2rem;
  margin-bottom: 1rem;
}

.document__body :deep(p) {
  margin-bottom: 1rem;
}

.document-loading {
  max-width: 840px;
  margin: 0 auto;
  padding: 4rem 1.5rem;
  display: grid;
  gap: 1.25rem;
}

.skeleton {
  width: 100%;
  border-radius: 12px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.12), rgba(148, 163, 184, 0.24), rgba(148, 163, 184, 0.12));
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.skeleton--title {
  height: 48px;
}

.skeleton--line {
  height: 20px;
}

@keyframes shimmer {
  0% {
    background-position-x: 0;
  }
  100% {
    background-position-x: -200%;
  }
}

@media (max-width: 640px) {
  .document {
    padding: 2.5rem 1rem;
  }
}
</style>
