<template>
  <article class="card">
    <h3>{{ title }}</h3>
    <p>{{ snippet }}</p>
    <RouterLink :to="{ name: 'document-detail', params: { id } }">Ver detalhes</RouterLink>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  id: string;
  title: string;
  snippet: string;
}>();
</script>

<style scoped>
.card {
  background: rgba(30, 41, 59, 0.8);
  padding: 1rem;
  border-radius: 12px;
}
</style>
