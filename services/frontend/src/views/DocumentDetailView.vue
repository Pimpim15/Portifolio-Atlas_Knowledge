<template>
  <section class="document">
    <header>
      <RouterLink to="/">← Voltar</RouterLink>
      <h1>{{ document?.title }}</h1>
      <span class="version">v{{ document?.version }}</span>
    </header>
    <p class="tags">Tags: {{ document?.tags?.join(', ') }}</p>
    <article v-if="document" v-html="document.body"></article>
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
}

const route = useRoute();
const document = ref<DocumentDetail | null>(null);

const loadDocument = async () => {
  const { data } = await api.get(`/docs/${route.params.id}`);
  document.value = data;
};

onMounted(loadDocument);
</script>

<style scoped>
.document {
  max-width: 768px;
  margin: 0 auto;
  padding: 3rem 1.5rem;
}

header {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.version {
  background: rgba(14, 165, 233, 0.2);
  color: #38bdf8;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-weight: 600;
}

.tags {
  margin-top: 1rem;
  font-style: italic;
}
</style>
