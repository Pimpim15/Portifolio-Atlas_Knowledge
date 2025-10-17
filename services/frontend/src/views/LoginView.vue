<template>
  <main class="auth">
    <section class="card">
      <header>
        <h1>Atlas Knowledge</h1>
        <p>Seu headquarters de conhecimento institucional.</p>
      </header>
      <form @submit.prevent="onSubmit">
        <label>
          Email
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <label>
          Senha
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <label v-if="showMfaField">
          Código MFA
          <input v-model="mfaCode" type="text" inputmode="numeric" autocomplete="one-time-code" placeholder="000000" maxlength="6" />
        </label>
        <small v-if="showMfaField" class="hint">Abra seu autenticador e copie o código de 6 dígitos.</small>
        <button type="submit" :disabled="isLoading">
          {{ isLoading ? 'Entrando...' : 'Entrar' }}
        </button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
      <small class="hint">Use <strong>admin@acme.com</strong> e <strong>admin</strong> para acessar o ambiente de demonstração.</small>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../store/auth';

const router = useRouter();
const authStore = useAuthStore();
const email = ref('admin@acme.com');
const password = ref('admin');
const mfaCode = ref('');
const error = ref('');
const isLoading = ref(false);
const showMfaField = ref(false);

const onSubmit = async () => {
  error.value = '';
  isLoading.value = true;
  try {
    await authStore.login({
      email: email.value,
      password: password.value,
      mfa_code: mfaCode.value || undefined,
    });
    router.push({ name: 'home' });
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    error.value = detail ?? 'Não foi possível autenticar. Verifique as credenciais e tente novamente.';
    if (detail && detail.toLowerCase().includes('mfa code')) {
      showMfaField.value = true;
    }
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.auth {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem;
}

.card {
  width: min(420px, 100%);
  background: rgba(15, 23, 42, 0.78);
  border-radius: 24px;
  padding: clamp(2rem, 4vw, 3rem);
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 28px 65px rgba(8, 15, 35, 0.5);
  display: grid;
  gap: 1.5rem;
}

header h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 2.6rem);
}

header p {
  margin: 0.5rem 0 0;
  color: rgba(226, 232, 240, 0.75);
}

form {
  display: grid;
  gap: 1.2rem;
}

label {
  display: grid;
  gap: 0.75rem;
  font-weight: 600;
}

input {
  width: 100%;
  border: none;
  border-radius: 14px;
  padding: 0.85rem 1rem;
  background: rgba(15, 23, 42, 0.6);
  color: #f8fafc;
  border: 1px solid transparent;
  transition: border 0.2s ease, box-shadow 0.2s ease;
}

input:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.6);
  box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.12);
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.85rem 1.5rem;
  font-weight: 600;
  font-size: 1rem;
  background: linear-gradient(135deg, #38bdf8, #14b8a6);
  color: #0f172a;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

button:hover:enabled {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(14, 197, 215, 0.35);
}

.error {
  margin: 0;
  color: #fda4af;
}

.hint {
  margin: 0;
  color: rgba(226, 232, 240, 0.7);
}

.hint strong {
  color: #38bdf8;
}

@media (max-width: 480px) {
  .card {
    padding: 2rem 1.5rem;
  }
}
</style>
