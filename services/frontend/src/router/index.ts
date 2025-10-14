import { createRouter, createWebHistory, type NavigationGuardNext, type RouteLocationNormalized } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/documents/:id',
    name: 'document-detail',
    component: () => import('../views/DocumentDetailView.vue'),
    meta: { requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
) => {
  const isAuthenticated = Boolean(localStorage.getItem('atlas:access_token'));
  if (to.meta.requiresAuth && !isAuthenticated) {
    next({ name: 'login' });
    return;
  }
  next();
});

export default router;
