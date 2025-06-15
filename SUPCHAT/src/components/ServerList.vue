<template>
    <div class="server-list">
        <div
        class="server-icon"
        @click="selectServer('0')"
        @contextmenu.prevent="handlePrivateContextMenu"
        >
        <img src="../assets/img/private-messages.png" alt="Private Messages" />
    </div>
    <div
    class="server-icon"
    v-for="server in servers"
    :key="server.id"
    @click="selectServer(server.serverId)"
    @contextmenu.prevent="showContextMenu($event, server)"
    >
    <img :src="server.picture" alt="Server Picture" v-if="server.picture" />
</div>
</div>

<teleport to="body" v-if="manager">
    <div
    class="context-menu"
    v-show="contextMenu.visible"
    :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
    <button @click="openCreateServerPopup">Create Server</button>
    <button @click="editServer(contextMenu.server?.serverId)">Edit</button>
    <button @click="deleteServer(contextMenu.server?.serverId)">Delete</button>
    <button
    v-if="contextMenu.server && contextMenu.server.isPublic === false"
    @click="openInvitePopup(contextMenu.server.serverId)"
    >Create Invite Link</button>
</div>
</teleport>

<teleport to="body" v-if="manager">
    <div v-if="showCreateServerPopup" class="popup-edit-server">
        <h3>Create Server</h3>
        <form @submit.prevent="submitCreateServer">
            <label for="newServerName">Server Name:</label>
            <input type="text" v-model="newServerName" required />
            
            <label for="newServerDescription">Server Description:</label>
            <textarea v-model="newServerDescription" rows="3" placeholder="Enter server description"></textarea>
            
            <label for="newIsPublic">Is Public:</label>
            <input type="checkbox" v-model="newIsPublic" />
            
            <label>Server Image:</label>
            <PfpCropper v-model="newServerImage" />
            
            <button type="submit">Create</button>
            <button type="button" @click="showCreateServerPopup = false">Cancel</button>
        </form>
    </div>
</teleport>

<teleport to="body" v-if="manager">
    <div v-if="showPopup" class="popup-edit-server">
        <h3>Edit Server</h3>
        <form @submit.prevent="submitServerChanges(popupData)">
            <label for="serverName">Server Name:</label>
            <input type="text" v-model="popupData.serverName" required />
            
            <label for="serverDescription">Server Description:</label>
            <textarea v-model="popupData.serverDescription" rows="3" placeholder="Enter server description"></textarea>
            
            <label for="isPublic">Is Public:</label>
            <input type="checkbox" v-model="popupData.isPublic" />
            
            <label>Server Image:</label>
            <PfpCropper v-model="popupData.serverImage" :defaultPfpUrl="previewPfpUrl" />
            
            <fieldset>
                <legend>Default Permissions:</legend>
                <label>
                    <input type="checkbox" v-model="popupData.default_permissions.read" />
                    Read
                </label>
                <label>
                    <input type="checkbox" v-model="popupData.default_permissions.write" />
                    Write
                </label>
                <label>
                    <input type="checkbox" v-model="popupData.default_permissions.manage" />
                    Manage
                </label>
                <label>
                    <input type="checkbox" v-model="popupData.default_permissions.invite" />
                    Invite
                </label>
                <label>
                    <input type="checkbox" v-model="popupData.default_permissions.upload" />
                    Upload
                </label>
            </fieldset>
            
            <button type="submit">Save</button>
            <button type="button" @click="showPopup = false">Cancel</button>
        </form>
    </div>
</teleport>

<teleport to="body">
    <div v-if="showInvitePopup" class="popup-edit-server">
        <h3>Create Invite Link</h3>
        <form @submit.prevent="submitInvite">
            <label>Duration (minutes):</label>
            <input type="number" v-model.number="inviteDuration" min="1" max="10080" />
            <label>
                <input type="checkbox" v-model="inviteOneTime" />
                One-time use
            </label>
            <button type="submit">Generate Link</button>
            <button type="button" @click="showInvitePopup = false">Cancel</button>
        </form>
        <div v-if="inviteUrl" style="margin-top:10px;">
            <strong>Invite URL:</strong>
            <input type="text" :value="inviteUrl" readonly style="width:100%;" />
        </div>
    </div>
</teleport>
</template>

<script>
import axios from 'axios';
import { inject } from 'vue';
import PfpCropper from './PfpCropper.vue';

export default {
    name: 'ServerList',
    props: {
        fastApiUrl: {
            type: String,
            default: 'http://127.0.0.1:8000'
        },
        userId: { type: String, required: true }
    },
    emits: ['server-selected'],
    components: { PfpCropper },
    data() {
        return {
            servers: {}, 
            previewPfpUrl: "",
            contextMenu: {
                visible: false,
                x: 0,
                y: 0,
                server: null
            },
            showPopup: false,
            popupData: {
                serverName: '',
                serverDescription: '',
                isPublic: false,
                serverImage: null,
                default_permissions: {
                    read: false,
                    write: false,
                    manage: false,
                    invite: false,
                    upload: false
                }
            },
            popupServerId: null,
            manager: false,
            showCreateServerPopup: false,
            newServerName: '',
            newServerDescription: '',
            newIsPublic: false,
            newServerImage: null,
            showInvitePopup: false,
            inviteServerId: null,
            inviteDuration: 1440,
            inviteOneTime: true,
            inviteUrl: ''
        };
    },
    async created() {
        await this.fetchServers();
    },
    mounted() {
        document.addEventListener('click', this.hideContextMenu);
        window.addEventListener('ws-message', this.handleWsMessage);
        this.checkMangaer()
    },
    beforeUnmount() {
        document.removeEventListener('click', this.hideContextMenu);
        window.removeEventListener('ws-message', this.handleWsMessage);
    },
    setup(props, { expose }) {
        const ws = inject('ws');
        expose({ ws });
        return { ws };
    },
    methods: {
        async checkMangaer() {
            try {
                const response = await axios.get(`${this.fastApiUrl}/users/me`);
                if (response.data.permissions.superuser) {
                    this.manager = true; 
                } else {
                    this.manager = false;
                }
            } catch (error) {
                console.error('Failed to check manager status:', error);
                this.manager = false;
            }
        },
        async fetchServers() {
            await new Promise(resolve => setTimeout(resolve, 200));
            try {
                this.servers = {};
                const response = await axios.get(`${this.fastApiUrl}/servers`, {
                });
                console.log('Fetched servers:', response.data);
                if (!Array.isArray(response.data)) {
                    throw new Error('Invalid server data format');
                }
                for (const server of response.data) {
                    this.servers[server.serverId] = server;
                }
                for (const server of Object.values(this.servers)) {
                    const serverId = server.serverId;
                    const serverResponse = await axios.get(`${this.fastApiUrl}/servers/${serverId}/picture`, {
                        responseType: 'blob'
                    });
                    const mimeType = serverResponse.headers['content-type'];
                    const blob = new Blob([serverResponse.data], { type: mimeType });
                    const url = URL.createObjectURL(blob);
                    server.picture = url;
                }
            } catch (error) {
                console.error('Failed to fetch servers:', error);
            }
        },
        showContextMenu(event, server) {
            const menuWidth = 180;
            const menuHeight = 160;
            const padding = 8;
            
            let x = event.clientX;
            let y = event.clientY;
            
            if (x + menuWidth > window.innerWidth - padding) {
                x = window.innerWidth - menuWidth - padding;
            }
            if (y + menuHeight > window.innerHeight - padding) {
                y = window.innerHeight - menuHeight - padding;
            }
            
            this.contextMenu.visible = true;
            this.contextMenu.x = x;
            this.contextMenu.y = y;
            this.contextMenu.server = server;
        },
        hideContextMenu() {
            this.contextMenu.visible = false;
            this.contextMenu.server = null;
        },
        async deleteServer(serverId) {
            try {
                await axios.delete(`${this.fastApiUrl}/servers/${serverId}/delete`, {
                });
                
                const serverName = this.servers[serverId].serverName;
                const confirmation = prompt(`Type the server name "${serverName}" to confirm deletion:`);
                if (confirmation === serverName) {
                    await axios.delete(`${this.fastApiUrl}/servers/${serverId}/confirm`, {
                    });
                } else {
                    alert('Server name does not match. Deletion cancelled.');
                }
            } catch (error) {
                console.error('Failed to delete server:', error);
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
            this.fetchServers();
            this.hideContextMenu();
        },
        
        async editServer(serverId) {
            try {
                const pfpRes = await axios.get(`${this.fastApiUrl}/servers/${serverId}/picture`, { responseType: 'blob' });
                this.previewPfpUrl = URL.createObjectURL(pfpRes.data);
            } catch {
                this.previewPfpUrl = '';
            }
            this.popupServerId = serverId;
            this.popupData = this.servers[serverId];
            this.showPopup = true;
            this.hideContextMenu();
        },
        async submitServerChanges(popupData) {
            try {
                const serverId = this.popupServerId;
                const formData = new FormData();
                formData.append('server_name', popupData.serverName);
                formData.append('server_description', popupData.serverDescription);
                formData.append('is_public', popupData.isPublic);
                
                if (
                popupData.serverImage &&
                (popupData.serverImage instanceof File || popupData.serverImage instanceof Blob)
                ) {
                    formData.append('server_image', popupData.serverImage);
                }
                
                const defaultPermissionsJson = JSON.stringify(popupData.default_permissions);
                formData.append('default_permissions', defaultPermissionsJson);
                
                for (const pair of formData.entries()) {
                    console.log(`${pair[0]}:`, pair[1]);
                }
                
                const response = await axios.put(`${this.fastApiUrl}/servers/${serverId}`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });
                
                console.log('Server updated:', response.data);
                await new Promise(resolve => setTimeout(resolve, 1000));
                await this.fetchServers();
            } catch (error) {
                console.error('Failed to update server:', error);
            } finally {
                this.showPopup = false;
            }
        },
        handleImageUpload(event) {
            const file = event.target.files[0];
            if (file) {
                this.popupData.serverImage = file;
            }
        },
        selectServer(serverId) {
            console.log('Selected server ID:', serverId);
            let info = [serverId, this.servers[serverId]];
            this.$emit('server-selected', info)
        },
        async handleWsMessage(event) {
            const data = event.detail;
            if (data.type === 'server_edit') {
                await this.fetchServers();
            }
        },
        openCreateServerPopup() {
            this.contextMenu.visible = false;
            this.showCreateServerPopup = true;
            this.newServerName = '';
            this.newServerDescription = '';
            this.newIsPublic = false;
            this.newServerImage = null;
        },
        onNewServerImageChange(event) {
            this.newServerImage = event.target.files[0];
        },
        async submitCreateServer() {
            try {
                const formData = new FormData();
                formData.append('server_name', this.newServerName);
                formData.append('server_description', this.newServerDescription);
                formData.append('is_public', this.newIsPublic);
                if (this.newServerImage) {
                    formData.append('server_image', this.newServerImage);
                }
                await axios.post(`${this.fastApiUrl}/servers`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
                this.showCreateServerPopup = false;
                await this.fetchServers();
            } catch (error) {
                alert('Failed to create server: ' + (error.response?.data?.detail || error.message));
            }
        },
        openInvitePopup(serverId) {
            this.showInvitePopup = true;
            this.inviteServerId = serverId;
            this.inviteDuration = 1440;
            this.inviteOneTime = true;
            this.inviteUrl = '';
            this.hideContextMenu();
        },
        async submitInvite() {
            try {
                const formData = new FormData();
                formData.append('duration_minutes', this.inviteDuration);
                formData.append('one_time', this.inviteOneTime);
                formData.append('send_email', false);
                formData.append('target_email', "");
                const response = await axios.post(
                `${this.fastApiUrl}/servers/${this.inviteServerId}/invite`,
                formData
                );
                this.inviteUrl = response.data.invite_url.replace('<appAddress>', window.location.origin);
                } catch (error) {
                    alert('Failed to create invite: ' + (error.response?.data?.detail || error.message));
                }
            },
            handlePrivateContextMenu() {
                if (this.manager) {
                    this.openCreateServerPopup();
                }
            }
        }
    };
</script>

<style scoped>
.server-list {
    width: 5em;
    background-color: #2f3136;
    color: white;
    padding: 10px;
    overflow-y: hidden;
    overflow-x: hidden;
    height: 97%;
    /* position: fixed;*/
    left: 0;
    top: 0;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    border-right: 1px solid #ccc;
    box-shadow: 2px 0 5px rgba(0, 0, 0, 0.5);
    transition: background-color 0.3s;
    user-select: none;
    font-family: Arial, sans-serif;
    font-size: 14px;
    top: 0;
}
.server-icon > img {
    width: 50px;
    height: 50px;
    margin: 5px;
    border-radius: 50%;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.2s;
}
.server-icon:hover > img {
    transform: scale(1.1);
}
.context-menu {
    position: absolute;
    background-color: #2f3136;
    color: white;
    border: 1px solid #ccc;
    border-radius: 5px;
    padding: 10px;
    z-index: 10000;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    display: flex;
    flex-direction: column;
}
.context-menu button {
    background: none;
    border: none;
    color: white;
    padding: 5px 10px;
    text-align: left;
    cursor: pointer;
    width: 100%;
}
.context-menu button:hover {
    background-color: #40444b;
}
.popup-edit-server {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background-color: #2f3136;
    color: white;
    padding: 20px;
    border-radius: 5px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    z-index: 10000;
}
.popup-edit-server h3 {
    margin: 0 0 10px;
}
.popup-edit-server form {
    display: flex;
    flex-direction: column;
}
@media (prefers-color-scheme: light) {
    .server-list,
    .popup-edit-server,
    .context-menu {
        background: #fff !important;
        color: #23272a !important;
        border-color: #cfd8dc !important;
    }
    .server-icon > img {
        border: 2px solid #5865f2;
        background: #fff;
    }
    .context-menu button {
        color: #23272a !important;
    }
    .context-menu button:hover {
        background: #e0e4fa !important;
        color: #5865f2 !important;
    }
    .popup-edit-server {
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
    }
}
</style>