<template>
  <div class="layout">
    <header class="top-bar">
      <RouterLink to="/">Atlas Knowledge</RouterLink>
      <slot name="actions" />
    </header>
    <main>
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  padding: 1rem 2rem;
  background: #1e293b;
}

main {
  flex: 1;
}
</style>
