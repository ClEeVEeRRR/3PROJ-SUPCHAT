<template>
    <div class="user-list">
        <!-- User list content -->
    </div>
</template>

<script>
import { inject } from 'vue';

export default {
    name: 'UserList',
    props: {
        fastApiUrl: {
            type: String,
            default: 'http://127.0.0.1:8000'
        },
    },
    setup(props, { expose }) {
        const ws = inject('ws');
        expose({ ws });
        return { ws };
    },
    data() {
        return {
        }
    },
    methods: {
    },
}
</script>

<style scoped>
.user-list {
    width: 240px;
    background-color: #2f3136;
}

@media (prefers-color-scheme: light) {
    .user-list {
        background: #fff !important;
        color: #23272a !important;
        border-color: #cfd8dc !important;
    }
}
</style>