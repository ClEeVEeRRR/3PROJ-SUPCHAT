<template>
    <div class="invite-handler">
        <div v-if="loading">Loading invite...</div>
        <div v-else-if="error">{{ error }}</div>
        <div v-else>
            <h2>You've been invited to join a server!</h2>
            <p>
                You've been invited by <b><u>{{ invite.createdByUsername || invite.createdBy }}</u></b> to <b><u>{{ invite.serverName || invite.serverId }}</u></b>.
            </p>
            <p v-if="invite.oneTime && invite.used">This invite has already been used.</p>
            <p v-else-if="expired">This invite has expired.</p>
            <button v-else @click="acceptInvite">Accept Invite</button>
        </div>
    </div>
</template>

<script>
import axios from 'axios';
export default {
    props: {
        fastApiUrl: {
            type: String,
            default: 'http://127.0.0.1:8000'
        },
    },
    data() {
        return {
            invite: null,
            loading: true,
            error: '',
            expired: false,
        };
    },
    async mounted() {
        try {
            const { inviteId } = this.$route.params;
            const res = await axios.get(`${this.fastApiUrl}/invite/${inviteId}`);
            this.invite = res.data;
            try {
                const userRes = await axios.get(`${this.fastApiUrl}/users/${this.invite.createdBy}`);
                this.invite.createdByUsername = userRes.data.username;
            } catch {
                console.warn('Could not fetch creator username');
            }
            try {
                const serverRes = await axios.get(`${this.fastApiUrl}/servers/${this.invite.serverId}`);
                console.log('Server data:', serverRes.data);
                this.invite.serverName = serverRes.data.serverName;
            } catch {
                console.warn('Could not fetch server name');
            }
            const now = new Date();
            console.log('Invite data:', this.invite);
            this.expired = now > new Date(this.invite.expiresAt);
        } catch (e) {
            this.error = e.response?.data?.detail || 'Invalid invite.';
        } finally {
            this.loading = false;
        }
    },
    methods: {
        async acceptInvite() {
            this.loading = true;
            this.error = '';
            try {
                const { inviteId } = this.$route.params;
                await axios.post(`${this.fastApiUrl}/invite/${inviteId}/accept`);
                this.invite.used = true;
                this.$emit('invite-accepted');
                alert('You have joined the server!');
                this.$router.replace({ path: '/' });
            } catch (e) {
                this.error = e.response?.data?.detail || 'Failed to accept invite.';
            } finally {
                this.loading = false;
            }
        }
    }
};
</script>

<style scoped>
.invite-handler {
    position: fixed;
    top: 40px;
    left: 50%;
    transform: translateX(-50%);
    min-width: 320px;
    max-width: 90vw;
    background: #23272a;
    color: #fff;
    border-radius: 10px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    padding: 32px 24px 24px 24px;
    z-index: 10000;
    text-align: center;
    border: 2px solid #5865f2;
    font-size: 1.1em;
}
.invite-handler button {
    margin-top: 16px;
    background: #5865f2;
    color: #fff;
    border: none;
    border-radius: 5px;
    padding: 10px 24px;
    font-size: 1em;
    cursor: pointer;
    transition: background 0.2s;
}
.invite-handler button:hover {
    background: #4752c4;
}
</style>