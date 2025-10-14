<template>
  <Teleport to="body" v-if="props.show">
    <div class="overlay" @click.self="emit('close')">
      <div class="panel" role="dialog" aria-modal="true">
        <header v-if="$slots.title" class="panel__header">
          <slot name="title" />
        </header>
        <section class="panel__body">
          <slot />
        </section>
        <footer v-if="$slots.actions" class="panel__footer">
          <slot name="actions" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue';

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ (event: 'close'): void }>();

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    emit('close');
  }
};

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(6px);
  z-index: 1000;
  padding: 2rem;
}

.panel {
  width: min(640px, 100%);
  background: linear-gradient(160deg, rgba(15, 23, 42, 0.95), rgba(30, 64, 175, 0.85));
  border-radius: 20px;
  box-shadow: 0 24px 64px rgba(8, 15, 35, 0.45);
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.25);
  overflow: hidden;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.panel__header {
  padding: 1.5rem 1.75rem 0.75rem;
  font-size: 1.35rem;
  font-weight: 700;
}

.panel__body {
  padding: 0 1.75rem 1.75rem;
  overflow-y: auto;
}

.panel__footer {
  padding: 1rem 1.75rem 1.5rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.15);
}
</style>
