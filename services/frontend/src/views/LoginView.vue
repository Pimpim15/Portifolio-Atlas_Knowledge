<template>
  <div class="auth">
    <h1>Atlas Knowledge</h1>
    <form @submit.prevent="onSubmit">
      <label>
        Email
        <input v-model="email" type="email" required />
      </label>
      <label>
        Senha
        <input v-model="password" type="password" required />
      </label>
      <button type="submit">Entrar</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../store/auth';

const router = useRouter();
const authStore = useAuthStore();
const email = ref('admin@acme.com');
const password = ref('admin');
const error = ref('');

const onSubmit = async () => {
  try {
    await authStore.login({ email: email.value, password: password.value });
    router.push({ name: 'home' });
  } catch (err) {
    error.value = (err as Error).message;
  }
};
</script>

<style scoped>
.auth {
  max-width: 360px;
  margin: 10vh auto;
  padding: 2rem;
  background: rgba(15, 23, 42, 0.8);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(15, 23, 42, 0.6);
}

label {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
  font-weight: 600;
}

input {
  margin-top: 0.25rem;
  padding: 0.75rem;
  border-radius: 8px;
  border: none;
}

button {
  width: 100%;
  padding: 0.75rem;
  background: #38bdf8;
  border: none;
  border-radius: 8px;
  color: #0f172a;
  font-weight: 700;
  cursor: pointer;
}

.error {
  color: #f87171;
  margin-top: 1rem;
}
</style>
