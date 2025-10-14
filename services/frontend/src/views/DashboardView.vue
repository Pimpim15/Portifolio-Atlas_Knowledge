<template>
  <main class="dashboard">
    <header>
      <h1>Bem-vindo ao Atlas Knowledge</h1>
      <button @click="handleLogout">Sair</button>
    </header>
    <section class="search">
      <input v-model="query" placeholder="Busque por runbooks, políticas, RFCs..." />
      <button @click="performSearch">Buscar</button>
    </section>
    <section class="results">
      <article v-for="doc in results" :key="doc.id" class="card">
        <h2>{{ doc.title }}</h2>
        <p>{{ doc.snippet }}</p>
        <RouterLink :to="{ name: 'document-detail', params: { id: doc.id } }">Abrir</RouterLink>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../utils/api';
import { useAuthStore } from '../store/auth';

const router = useRouter();
const authStore = useAuthStore();
const query = ref('');
const results = ref<{ id: string; title: string; snippet: string }[]>([]);

const performSearch = async () => {
  const { data } = await api.get('/search', { params: { q: query.value } });
  results.value = data.results;
};

const handleLogout = () => {
  authStore.logout();
  router.push({ name: 'login' });
};
</script>

<style scoped>
.dashboard {
  padding: 2rem 4rem;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
}

.results {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}

.card {
  background: rgba(15, 23, 42, 0.7);
  border-radius: 12px;
  padding: 1.5rem;
}
</style>
