import { createRouter, createWebHistory } from 'vue-router';
import InviteHandler from '../components/InviteHandler.vue';

const routes = [
    { path: '/invite/:inviteId', component: InviteHandler, name: 'InviteHandler' }
];

const router = createRouter({
    history: createWebHistory(),
    routes,
});

export default router;