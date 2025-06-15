<template>
    <transition name="fade-overlay">
        <div v-if="loading" class="loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">Loading...</div>
        </div>
    </transition>
    <div class="app" v-if="!loading">
        <router-view v-slot="{ Component }">
            <component :is="Component" :fastApiUrl="fastApiUrl['value']" />
        </router-view>
        <Login v-if="!auth" @login-success="setAuth" :fastApiUrl="fastApiUrl['value']" :error="loginError"/>
        <div v-else class="main-content">
            <ServerList :fastApiUrl="fastApiUrl['value']" :userId="userId" @server-selected="handleServerSelected" />
            <RoomList
            :fastApiUrl="fastApiUrl['value']"
            :selectedServerId="selectedServerId"
            :selectedServerInfo="selectedServerInfo"
            :userId="userId"
            @room-selected="handleRoomSelected"
            :width="roomListWidth"
            />
            <div
            class="vertical-resizer"
            @mousedown="startResizing"
            ></div>
            <ChatWindow
            v-if="selectedRoomId"
            :fastApiUrl="fastApiUrl['value']"
            :serverId="selectedServerId"
            :roomId="selectedRoomId"
            :userId="userId"
            :selectedServerInfo="selectedServerInfo"
            :selectedRoomId="selectedRoomId"
            :windowStyle="{ minWidth: '200px', width: 'calc(100% - ' + (roomListWidth + 6) + 'px)' }"
            />
        </div>
        <button v-if="auth && isSuperuser" class="superadmin-btn" @click="showSuperAdmin = true">SuperAdmin</button>
        <div
        v-if="auth"
        class="profile-avatar-fab"
        @click="showProfileEdit = true"
        @mouseenter="profileFabHovered = true"
        @mouseleave="profileFabHovered = false"
        :class="{ expanded: profileFabHovered }"
        >
        <img
        :src="userProfilePicUrl"
        alt="Profile"
        class="profile-avatar-img"
        @error="onProfileImgError"
        />
        <transition name="fade">
            <div v-if="profileFabHovered" class="profile-avatar-info">
                <div class="profile-avatar-username">{{ userProfile?.username }}</div>
                <div class="profile-avatar-email">{{ userProfile?.email }}</div>
            </div>
        </transition>
        <transition name="fade">
            <button
            v-if="profileFabHovered"
            class="logout-fab-btn"
            @click.stop="logout"
            title="Disconnect"
            >
            <svg fill="#ffffff" version="1.1" id="Capa_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="64px" height="64px" viewBox="-98.5 -98.5 689.50 689.50" xml:space="preserve" stroke="#ffffff"><g id="SVGRepo_bgCarrier" stroke-width="0"><rect x="-98.5" y="-98.5" width="689.50" height="689.50" rx="344.75" fill="#ff0000" strokewidth="0"></rect></g><g id="SVGRepo_tracerCarrier" stroke-linecap="round" stroke-linejoin="round"></g><g id="SVGRepo_iconCarrier"> <g> <path d="M184.646,0v21.72H99.704v433.358h31.403V53.123h53.539V492.5l208.15-37.422v-61.235V37.5L184.646,0z M222.938,263.129 c-6.997,0-12.67-7.381-12.67-16.486c0-9.104,5.673-16.485,12.67-16.485s12.67,7.381,12.67,16.485 C235.608,255.748,229.935,263.129,222.938,263.129z"></path> </g> </g></svg>
        </button>
    </transition>
</div>
<SuperAdmin
v-if="showSuperAdmin"
:fastApiUrl="fastApiUrl['value']"
@close="showSuperAdmin = false"
/>
<UserProfileEdit
v-if="showProfileEdit"
:fastApiUrl="fastApiUrl['value']"
:userId="userId"
@close="showProfileEdit = false"
/>
</div>
</template>

<script>
import { ref, onMounted, onUnmounted, provide, watch } from 'vue';
import Login from './components/Login.vue';
import ServerList from './components/ServerList.vue';
import RoomList from './components/RoomList.vue';
import ChatWindow from './components/ChatWindow.vue';
import UserList from './components/UserList.vue';
import SuperAdmin from './components/SuperAdminPannel.vue';
import UserProfileEdit from './components/UserProfileEdit.vue';
import axios from 'axios';

function getAuthHeader() {
    return (
    localStorage.getItem('auth') ||
    sessionStorage.getItem('auth') ||
    null
    );
}

axios.interceptors.request.use(config => {
    const auth = getAuthHeader();
    if (auth) {
        config.headers['Authorization'] = `Basic ${auth}`;
    }
    return config;
});

const errorMessage = "Something went wrong with your infos since last session!!!\nThis is most likely related to a recent passsword change.\nIf you did not change your password please contact your Platform Superadmin :)";

let setAuthRef = null;

axios.interceptors.response.use(
response => response,
error => {
    console.log('Error response:', error);
    if (
    error.response &&
    error.response.status === 500 &&
    error.response.data &&
    typeof error.response.data.detail === 'string' &&
    (
    error.response.data.detail.toLowerCase().includes('credentials') ||
    error.response.data.detail.toLowerCase().includes('auth') ||
    error.response.data.detail.toLowerCase().includes('password') ||
    error.response.data.detail.toLowerCase().includes('username')
    )
    ) {
        if (setAuthRef) setAuthRef(null, errorMessage);
        localStorage.removeItem('auth');
        sessionStorage.removeItem('auth');
    }
    return Promise.reject(error);
}
);

export default {
    name: 'App',
    components: {
        Login,
        ServerList,
        RoomList,
        ChatWindow,
        UserList,
        SuperAdmin,
        UserProfileEdit,
    },
    setup() {
        let fastApiUrl = ref('http://127.0.0.1:8000');
        const selectedServerId = ref("0");
        const selectedServerInfo = ref(null);
        const selectedRoomId = ref(null);
        const auth = ref(getAuthHeader());
        const loginError = ref('');
        const ws = ref(null);
        let pingInterval = null;
        let pongTimeout = null;
        const userId = ref(null);
        const roomListWidth = ref(300);
        let resizing = false;
        const showSuperAdmin = ref(false);
        const isSuperuser = ref(false);
        const showProfileEdit = ref(false);
        const profileFabHovered = ref(false);
        const userProfile = ref(null);
        const userProfilePicUrl = ref('/assets/img/examplepfp/pfp1.png');
        const loading = ref(true);
        
        function setAuth(authObj, errorMsg) {
            if (!authObj) {
                loginError.value = errorMsg || '';
                auth.value = null;
                localStorage.removeItem('auth');
                sessionStorage.removeItem('auth');
                return;
            }
            const { credentials, rememberMe } = authObj;
            loginError.value = '';
            if (credentials) {
                if (rememberMe) {
                    localStorage.setItem('auth', credentials);
                    sessionStorage.removeItem('auth');
                } else {
                    sessionStorage.setItem('auth', credentials);
                    localStorage.removeItem('auth');
                }
                // auth.value = credentials;
            }
            window.location.reload();
        }
        
        async function fetchUserId() {
            try {
                const res = await axios.get(fastApiUrl.value+'/users/me');
                console.log("Fetched user ID:", res.data);
                userId.value = res.data.id || res.data.userId || res.data._id;
                isSuperuser.value = !!res.data.permissions?.superuser;
                userProfilePicUrl.value = res.data.profilePicUrl || '';
                userProfile.value = res.data;
            } catch (e) {
                userId.value = null;
                isSuperuser.value = false;
            }
        }
        
        async function onProfileImgError(e) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            fetchUserProfile()
        }
        
        async function fetchUserProfile() {
            console.log("Fetching user profile for userId:", userId.value);
            if (!auth || !userId.value) return;
            try {
                const res = await axios.get(`${fastApiUrl.value}/users/${userId.value}`);
                userProfile.value = res.data;
                try {
                    const pfpRes = await axios.get(`${fastApiUrl.value}/users/${userId.value}/profile_picture`, { responseType: 'blob' });
                    const url = URL.createObjectURL(pfpRes.data);
                    userProfilePicUrl.value = url;
                } catch {
                    userProfilePicUrl.value = '/assets/img/examplepfp/pfp1.png';
                }
            } catch {
                userProfile.value = { username: 'Unknown', email: '' };
                userProfilePicUrl.value = '/assets/img/examplepfp/pfp1.png';
            }
        }
        
        setAuthRef = setAuth;
        
        watch(auth, (val) => {
            if (val) fetchUserId();
            else userId.value = null;
        }, { immediate: true });
        
        watch(showProfileEdit, (val) => { if (!val) fetchUserProfile(); });
        
        function handleServerSelected(info) {
            const serverId = info[0];
            const serverInfo = info[1];
            selectedServerId.value = serverId;
            selectedServerInfo.value = serverInfo;
        }
        
        function handleRoomSelected(roomId) {
            selectedRoomId.value = roomId;
        }
        
        function logout() {
            auth.value = null;
            localStorage.removeItem('auth');
            sessionStorage.removeItem('auth');
        }
        
        function setupWebSocket() {
            if (ws.value) ws.value.close();
            ws.value = new WebSocket("ws://localhost:8000/ws");
            
            ws.value.onopen = () => {
                console.log("WebSocket connected");
                startPing();
            };
            ws.value.onclose = () => {
                console.log("WebSocket closed");
                stopPing();
                reconnectWebSocket();
            };
            ws.value.onerror = (e) => {
                console.error("WebSocket error", e);
                stopPing();
                reconnectWebSocket();
            };
            ws.value.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'pong') {
                    if (pongTimeout) {
                        clearTimeout(pongTimeout);
                        pongTimeout = null;
                    }
                } else {
                    window.dispatchEvent(new CustomEvent('ws-message', { detail: data }));
                }
            };
        }
        
        function startPing() {
            stopPing();
            pingInterval = setInterval(() => {
                if (ws.value && ws.value.readyState === 1) {
                    try {
                        ws.value.send(JSON.stringify({ type: 'ping' }));
                        pongTimeout = setTimeout(() => {
                            console.warn("WebSocket pong not received, reconnecting...");
                            ws.value.close();
                        }, 5000);
                    } catch (e) {
                        console.error("Ping failed, reconnecting...", e);
                        ws.value.close();
                    }
                }
            }, 15000);
        }
        
        function stopPing() {
            if (pingInterval) clearInterval(pingInterval);
            pingInterval = null;
            if (pongTimeout) clearTimeout(pongTimeout);
            pongTimeout = null;
        }
        
        function reconnectWebSocket() {
            setTimeout(() => {
                setupWebSocket();
            }, 2000);
        }
        
        function startResizing(e) {
            resizing = true;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        }
        function stopResizing() {
            resizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
        function resize(e) {
            if (!resizing) return;
            const serverListWidth = 5 * 16;
            const min = 160, max = 500;
            let newWidth = e.clientX - serverListWidth;
            if (newWidth < min) newWidth = min;
            if (newWidth > max) newWidth = max;
            roomListWidth.value = newWidth;
        }
        
        onMounted(() => {
            if (window.api && typeof window.api.getApiAddress === 'function') {
                window.api.getApiAddress().then(apiAddress => {
                    if (typeof apiAddress === 'string' && apiAddress.trim()) {
                        fastApiUrl.value = apiAddress.trim();
                    } else {
                        console.warn('API address not found, using default:', fastApiUrl.value);
                    }
                });
            }
            window.addEventListener('mousemove', resize);
            window.addEventListener('mouseup', stopResizing);
            setupWebSocket();
            
            setTimeout(async () => {
                await fetchUserProfile();
                loading.value = false;
            }, 200);
            
        });
        onUnmounted(() => {
            window.removeEventListener('mousemove', resize);
            window.removeEventListener('mouseup', stopResizing);
            if (ws.value) ws.value.close();
            stopPing();
        });
        
        provide('ws', ws);
        
        return {
            fastApiUrl,
            selectedServerId,
            selectedServerInfo,
            selectedRoomId,
            auth,
            setAuth,
            handleServerSelected,
            handleRoomSelected,
            logout,
            loginError,
            userId,
            roomListWidth,
            startResizing,
            ws,
            showSuperAdmin,
            isSuperuser,
            showProfileEdit,
            profileFabHovered,
            userProfilePicUrl,
            userProfile,
            loading,
        };
    }
};
</script>

<style scoped>
.app {
    height: 100vh;
    width: 100vw;
    overflow: hidden;
    position: relative;
}
.main-content {
    display: flex;
    height: 100%;
    width: 100vw;
    overflow: unset;
}
.logout-btn {
    position: absolute;
    top: 10px;
    right: 10px;
    background: #5865f2;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
    z-index: 10;
}
.logout-btn:hover {
    background: #4752c4;
}
.vertical-resizer {
    width: 6px;
    cursor: col-resize;
    background: #23272a;
    transition: background 0.2s;
    z-index: 2;
    height: 100vh;
}
.vertical-resizer:hover {
    background: #5865f2;
}
.superadmin-btn {
    position: absolute;
    bottom: 10px;
    left: 10px;
    background: #ffb347;
    color: #23272a;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
    z-index: 11;
    font-weight: bold;
    z-index: 1001;
}
.superadmin-btn:hover {
    background: #ffe066;
}
.profile-avatar-fab {
    position: fixed;
    top: 24px;
    right: 24px;
    display: flex;
    align-items: center;
    background: #23272a;
    border-radius: 32px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    cursor: pointer;
    padding: 6px 12px 6px 6px;
    z-index: 1002;
    min-width: 48px;
    width: 56px;
    max-width: 320px;
    overflow: hidden;
    transition: width 0.3s cubic-bezier(.4,0,.2,1), right 0.25s, box-shadow 0.2s;
}
.profile-avatar-fab.expanded {
    width: 240px;
    right: 24px;
    background: #23272a;
    box-shadow: 0 6px 24px rgba(0,0,0,0.32);
}
.profile-avatar-info {
    display: flex;
    flex-direction: column;
    margin-left: 16px;
    min-width: 0;
    flex: 1;
    overflow: hidden;
}
.logout-fab-btn {
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
    cursor: pointer;
    z-index: 1003;
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
}
.logout-fab-btn:hover svg circle {
    fill: #c0392b;
}
.profile-avatar-img {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #7289da;
    background: #23272a;
    transition: box-shadow 0.2s;
}
.profile-avatar-username {
    font-weight: bold;
    font-size: 1.1em;
    color: #fff;
}
.profile-avatar-email {
    font-size: 0.85em;
    color: #aaa;
    margin-top: 2px;
}
.fade-enter-active, .fade-leave-active {
    transition: opacity 0.18s;
}
.fade-enter-from, .fade-leave-to {
    opacity: 0;
}
.fade-overlay-enter-active, .fade-overlay-leave-active {
    transition: opacity 0.4s;
}
.fade-overlay-enter-from, .fade-overlay-leave-to {
    opacity: 0;
}
.fade-overlay-enter-to, .fade-overlay-leave-from {
    opacity: 1;
}
.loading-overlay {
    position: fixed;
    z-index: 999999;
    inset: 0;
    background: #23272a;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.loading-spinner {
    border: 6px solid #444;
    border-top: 6px solid #7289da;
    border-radius: 50%;
    width: 64px;
    height: 64px;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
}
@keyframes spin {
    0% { transform: rotate(0deg);}
    100% { transform: rotate(360deg);}
}
.loading-text {
    color: #fff;
    font-size: 1.3em;
    letter-spacing: 0.05em;
}
@media (prefers-color-scheme: light) {
    .app, .main-content, .loading-overlay {
        background: #f7fafd !important;
        color: #23272a !important;
    }
    .profile-avatar-username {
        font-weight: bold;
        font-size: 1.1em;
        color: #23272a;
    }
    .profile-avatar-email {
        font-size: 0.85em;
        color: #585858;
        margin-top: 2px;
    }
    .profile-avatar-fab,
    .profile-avatar-fab.expanded {
        background: #fff !important;
        color: #23272a !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .profile-avatar-img {
        border: 2px solid #5865f2;
        background: #fff;
    }
    .vertical-resizer {
        background: #e0e4fa;
    }
    .vertical-resizer:hover {
        background: #5865f2;
    }
    .superadmin-btn {
        background: #ffe066;
        color: #23272a;
    }
    .superadmin-btn:hover {
        background: #ffb347;
    }
    .loading-overlay {
        background: #fff;
    }
    .loading-spinner {
        border: 6px solid #ddd;
        border-top: 6px solid #7289da;
    }
    .loading-text {
        color: #23272a;
    }
}
</style>