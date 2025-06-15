<template>
    <div class="room-list" :style="{ width: width + 'px' }" v-if="selectedServerId == '0'">
        <h1>Private Messages</h1>
        <!-- TODO -->
    </div>
    <div class="room-list" :style="{ width: width + 'px' }" v-else>
        <transition-group
        tag="ul"
        ref="roomList"
        class="room-list-ul"
        @mousemove="isReordering && onDrag($event)"
        @mouseup="isReordering && endDrag($event)"
        @mouseleave="isReordering && endDrag($event)"
        name="room-move"
        >
        <li class="name" :key="'server-name'" style="background-color: rgb(36, 36, 36); cursor: default;">
            {{ selectedServerInfo.serverName }}
            <button v-if="manager" class="reorder-button" @click="toggleReorderMode">
                %
            </button>
        </li>
        <li
        v-if="Object.keys(rooms).length === 0"
        :key="'no-rooms'"
        @contextmenu.prevent="manager ? createRoom() : null"
        :style="{ cursor: manager ? 'pointer' : 'not-allowed', color: manager ? '' : '#888' }"
        >
        {{ manager ? 'Right click to create a room' : 'No rooms available' }}
    </li>
    <template v-for="(room, idx) in orderedRooms" :key="room.roomId">
        <!-- <li
        v-if="isReordering && isDragging && hoverIndex === idx"
        :key="'drop-target-' + idx"
        class="room-list-item drop-target"
        ></li> -->
        <li
        v-if="!isDragging || dragIndex !== idx"
        class="room-list-item"
        @click="handleRoomClick(room.roomId)"
        @contextmenu.prevent="showContextMenu($event, room)"
        >
        <span>{{ room.roomName }}</span>
        <button
        v-if="isReordering"
        class="drag-handle"
        @mousedown.prevent="startDrag(idx, $event)"
        @touchstart.prevent="startDrag(idx, $event)"
        >
        <svg width="20" height="20" viewBox="0 0 20 20">
            <rect y="4" width="20" height="2" rx="1" fill="#ccc"/>
            <rect y="9" width="20" height="2" rx="1" fill="#ccc"/>
            <rect y="14" width="20" height="2" rx="1" fill="#ccc"/>
        </svg>
    </button>
</li>
</template>
<!-- <li
v-if="isReordering && isDragging && hoverIndex === orderedRooms.length"
:key="'drop-target-end'"
class="room-list-item drop-target"
></li> -->
<li
v-if="isReordering && isDragging"
:key="'drop-zone-end'"
class="room-list-item drop-zone-end"
>
Move arround the rooms to their desired location then click on the "Confirm Order" button.
</li>
</transition-group>

<teleport to="body">
    <div
    class="context-menu"
    v-show="contextMenu.visible && manager"
    :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
    <button @click="editRoom(contextMenu.room.roomId)">Edit Room</button>
    <button @click="deleteRoom(contextMenu.room.roomId)">Delete Room</button>
    <button @click="createRoom()">Create Room</button>
    <button @click="openSetUserPermsPopup(contextMenu.room.roomId)">Set User Permissions</button>
</div>
</teleport>

<teleport to="body" v-if="manager">
    <div v-if="showPopup" class="popup-edit-room">
        <h3>{{ popupRoomId ? 'Edit Room' : 'Create Room' }}</h3>
        <form @submit.prevent="submitRoomChanges(popupData)">
            <label for="roomName">Room Name:</label>
            <input type="text" v-model="popupData.roomName" required />
            
            <label for="roomDescription">Room Description:</label>
            <textarea v-model="popupData.roomDescription" rows="3" placeholder="Enter room description"></textarea>
            
            <fieldset>
                <legend>Default Permissions:</legend>
                <label>
                    <input type="checkbox" v-model="popupData.default_permissions.invite" />
                    Invite
                </label>
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
                    <input type="checkbox" v-model="popupData.default_permissions.upload" />
                    Upload
                </label>
            </fieldset>
            
            <button type="submit">Save</button>
            <button type="button" @click="showPopup = false">Cancel</button>
        </form>
    </div>
</teleport>

<teleport to="body" v-if="setUserPermsPopup">
    <div class="popup-edit-room">
        <h3>Set User Permissions for Room</h3>
        <label>Select User:</label>
        <select v-model="selectedUser">
            <option v-for="user in userList" :key="user.userId" :value="user.userId">
                {{ user.username }}
            </option>
        </select>
        <fieldset v-if="selectedUser">
            <legend>Permissions for this room:</legend>
            <label><input type="checkbox" v-model="userRoomPerms.invite" /> Invite</label>
            <label><input type="checkbox" v-model="userRoomPerms.read" /> Read</label>
            <label><input type="checkbox" v-model="userRoomPerms.write" /> Write</label>
            <label><input type="checkbox" v-model="userRoomPerms.manage" /> Manage</label>
            <label><input type="checkbox" v-model="userRoomPerms.upload" /> Upload</label>
        </fieldset>
        <button @click="saveUserRoomPerms" :disabled="!selectedUser">Save</button>
        <button @click="setUserPermsPopup = false">Cancel</button>
    </div>
</teleport>

<div v-if="isReordering" class="reorder-controls">
    <button @click="confirmReorder">Confirm Order</button>
    <button @click="cancelReorder">Cancel</button>
</div>
</div>

<div
v-if="ghostRoom && isDragging"
class="ghost-room"
:style="{
    top: ghostY - 50 + 'px',
    left: ghostX - 50 + 'px',
    // transform: 'rotate(10deg)'
}"
>
<span>{{ ghostRoom.roomName }}</span>
</div>
</template>

<script>
import axios from 'axios';
import { inject } from 'vue';

export default {
    name: 'RoomList',
    props: {
        fastApiUrl: {
            type: String,
            default: 'http://127.0.0.1:8000'
        },
        selectedServerId: {
            type: String,
            required: true
        },
        selectedServerInfo: {
            type: Object,
            required: false
        },
        userId: { type: String, required: true },
        width: { type: Number, default: 240 }
    },
    emits: ['room-selected'],
    data() {
        return {
            rooms: {},
            orderedRooms: [],
            originalOrderedRooms: [],
            isReordering: false,
            dragIndex: null,
            dragOverIndex: null,
            isDragging: false,
            hoverIndex: null,
            contextMenu: {
                visible: false,
                x: 0,
                y: 0,
                room: null
            },
            showPopup: false,
            popupData: {
                roomName: '',
                roomDescription: '',
                default_permissions: {
                    invite: false,
                    read: false,
                    write: false,
                    manage: false,
                    upload: false
                }
            },
            popupRoomId: null,
            manager: false,
            ghostRoom: null,
            ghostY: 0,
            ghostX: 0,
            perms: {
                invite: false,
                read: false,
                write: false,
                manage: false,
                upload: false
            },
            setUserPermsPopup: false,
            userList: [],
            selectedUser: null,
            userRoomPerms: {
                invite: false,
                read: false,
                write: false,
                manage: false,
                upload: false
            },
            targetRoomId: null,
            roomPerms: {}
        };
    },
    watch: {
        selectedServerId: {
            immediate: true,
            handler(newServerId) {
                console.log('Selected server ID changed:', newServerId);
                if (newServerId != '0') {
                    this.rooms = {}; 
                    this.fetchRooms(newServerId);
                    this.getperms()
                } else {
                    this.rooms = {}; 
                }
            }
        }
    },
    mounted() {
        window.addEventListener('ws-message', this.handleWsMessage);
        // if (this.selectedServerId !== '0') {
        this.getperms()
        // }
    },
    beforeUnmount() {
        window.removeEventListener('ws-message', this.handleWsMessage);
    },
    setup(props, { expose }) {
        const ws = inject('ws');
        expose({ ws });
        return { ws };
    },
    methods: {
        async getperms() {
            let perms = await axios.get(`${this.fastApiUrl}/servers/${this.selectedServerId}/${this.userId}/permissions`)
            .catch(error => {
                console.error('Failed to fetch permissions:', error);
                return {
                    invite: false,
                    read: false,
                    write: false,
                    manage: false,
                    upload: false
                };
            });
            this.perms = perms.data || {
                invite: false,
                read: false,
                write: false,
                manage: false,
                upload: false
            }
            if (this.perms.manage || this.perms.superuser) {
                this.manager = true; 
            } else {
                this.manager = false;
            }
        },
        async fetchRooms(serverId) {
            try {
                const response = await axios.get(`${this.fastApiUrl}/rooms/${serverId}`);
                const serverResponse = await axios.get(`${this.fastApiUrl}/servers/${serverId}`);
                const roomOrder = serverResponse.data.rooms; 
                
                const roomMap = response.data.reduce((acc, room) => {
                    acc[room.roomId] = room;
                    return acc;
                }, {});
                
                if (Array.isArray(roomOrder)) {
                    this.orderedRooms = roomOrder
                        .map(id => roomMap[id])
                        .filter(room => room);
                } else {
                    this.orderedRooms = response.data;
                }
                this.originalOrderedRooms = [...this.orderedRooms];
                this.rooms = roomMap;

                this.roomPerms = {};
                await Promise.all(
                    this.orderedRooms.map(async room => {
                        try {
                            const permsRes = await axios.get(
                                `${this.fastApiUrl}/servers/${this.selectedServerId}/${room.roomId}/permissions`
                            );
                            this.$set(this.roomPerms, room.roomId, permsRes.data);
                        } catch (e) {
                            this.$set(this.roomPerms, room.roomId, {});
                        }
                    })
                );
            } catch (error) {
                console.error('Failed to fetch rooms:', error);
            }
        },
        toggleReorderMode() {
            if (this.isReordering) {
                this.cancelReorder();
            } else {
                this.isReordering = true;
                this.dragIndex = null;
                this.dragOverIndex = null;
                this.isDragging = false;
                this.hoverIndex = null;
                this.ghostRoom = null;
            }
        },
        startDrag(index, event) {
            this.dragIndex = index;
            this.dragOverIndex = index;
            this.isDragging = true;
            this.ghostRoom = this.orderedRooms[index];
            this.updateGhostPosition(event);
            document.addEventListener('mousemove', this.onDrag);
            document.addEventListener('mouseup', this.endDrag);
            document.addEventListener('touchmove', this.onDrag);
            document.addEventListener('touchend', this.endDrag);
        },
        onDrag(event) {
            if (!this.isDragging) return;
            this.updateGhostPosition(event);
            const ul = this.$refs.roomList.$el;
            const rect = ul.getBoundingClientRect();
            const clientY = event.touches ? event.touches[0].clientY : event.clientY;
            const y = clientY - rect.top;
            const items = Array.from(ul.children).filter(li => li.classList.contains('room-list-item'));
            let hoverIndex = items.findIndex(li => {
                const liRect = li.getBoundingClientRect();
                return y >= (liRect.top - rect.top) && y < (liRect.bottom - rect.top);
            });
            if (hoverIndex === -1) hoverIndex = this.orderedRooms.length;
            this.hoverIndex = hoverIndex;
        },
        endDrag(event) {
            if (!this.isDragging) return;
            if (this.hoverIndex !== null && this.hoverIndex !== this.dragIndex) {
                const tempRooms = [...this.orderedRooms];
                const [dragged] = tempRooms.splice(this.dragIndex, 1);
                tempRooms.splice(this.hoverIndex, 0, dragged);
                this.orderedRooms = tempRooms;
            }
            this.isDragging = false;
            this.dragIndex = null;
            this.hoverIndex = null;
            this.ghostRoom = null;
            document.removeEventListener('mousemove', this.onDrag);
            document.removeEventListener('mouseup', this.endDrag);
            document.removeEventListener('touchmove', this.onDrag);
            document.removeEventListener('touchend', this.endDrag);
        },
        async confirmReorder() {
            try {
                const roomOrder = this.orderedRooms.map(room => room.roomId);
                console.log('New room order:', roomOrder);
                
                await axios.put(
                `${this.fastApiUrl}/servers/${this.selectedServerId}/rooms`,
                roomOrder,
                { headers: { 'Content-Type': 'application/json' } }
                );
                
                console.log('Room order updated:', roomOrder);
                this.isReordering = false;
                this.ws.send(JSON.stringify({
                    type: 'room_edit',
                    serverId: this.selectedServerId
                }));
            } catch (error) {
                console.error('Failed to update room order:', error);
            }
        },
        cancelReorder() {
            this.isReordering = false;
            this.orderedRooms = [...this.originalOrderedRooms];
        },
        showContextMenu(event, room) {
            if (!this.manager) return;
            event.preventDefault();
            
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
            this.contextMenu.room = room;
            document.addEventListener('click', this.hideContextMenu);
        },
        hideContextMenu() {
            this.contextMenu.visible = false;
            this.contextMenu.room = null;
            document.removeEventListener('click', this.hideContextMenu);
        },
        createRoom() {
            if (!this.manager) return; 
            this.popupRoomId = null;
            this.popupData = {
                roomName: '',
                roomDescription: '',
                default_permissions: {
                    invite: false,
                    read: false,
                    write: false,
                    manage: false,
                    upload: false
                }
            };
            this.showPopup = true;
            this.hideContextMenu();
        },
        editRoom(roomId) {
            this.popupRoomId = roomId;
            this.popupData = { ...this.rooms[roomId] };
            this.showPopup = true;
            this.hideContextMenu();
        },
        async submitRoomChanges(popupData) {
            try {
                const perms = {
                    invite: false,
                    read: false,
                    write: false,
                    manage: false,
                    upload: false,
                    ...(popupData.default_permissions || {})
                };
                
                const formData = new FormData();
                formData.append('room_name', popupData.roomName);
                formData.append('room_description', popupData.roomDescription);
                formData.append('everyone_can_invite', perms.invite ? 'true' : 'false');
                formData.append('everyone_can_see', perms.read ? 'true' : 'false');
                formData.append('everyone_can_write', perms.write ? 'true' : 'false');
                formData.append('everyone_can_manage', perms.manage ? 'true' : 'false');
                formData.append('everyone_can_upload', perms.upload ? 'true' : 'false');
                
                if (this.popupRoomId) {
                    await axios.put(
                    `${this.fastApiUrl}/rooms/${this.selectedServerId}/${this.popupRoomId}`,
                    formData,
                    { headers: { 'Content-Type': 'multipart/form-data' } }
                    );
                } else {
                    await axios.post(
                    `${this.fastApiUrl}/rooms/${this.selectedServerId}`,
                    formData,
                    { headers: { 'Content-Type': 'multipart/form-data' } }
                    );
                }
                
                if (this.ws && this.ws.readyState === 1) {
                    this.ws.send(JSON.stringify({
                        type: 'room_edit',
                        serverId: this.selectedServerId
                    }));
                }
            } catch (error) {
                console.error('Failed to save room:', error);
            } finally {
                this.showPopup = false;
            }
        },
        async deleteRoom(roomId) {
            try {
                const room = this.rooms[roomId];
                await axios.delete(`${this.fastApiUrl}/rooms/${this.selectedServerId}/${roomId}/delete`);
                const confirmation = window.prompt(
                `Type the room name exactly to confirm deletion:\n"${room.roomName}"`
                );
                if (confirmation !== room.roomName) {
                    alert("Room name does not match. Deletion cancelled.");
                    return;
                }
                
                await axios.delete(`${this.fastApiUrl}/rooms/${this.selectedServerId}/${roomId}/confirm`);
                
                if (this.ws && this.ws.readyState === 1) {
                    this.ws.send(JSON.stringify({
                        type: 'room_edit',
                        serverId: this.selectedServerId
                    }));
                }
            } catch (error) {
                console.error('Failed to delete room:', error);
                alert("Failed to delete room: " + (error.response?.data?.detail || error.message));
            }
        },
        async saveUserRoomPerms() {
            if (!this.selectedUser) return;
            const formData = new FormData();
            formData.append('permissions', JSON.stringify(this.userRoomPerms));
            try {
                await axios.put(
                `${this.fastApiUrl}/rooms/${this.selectedServerId}/${this.targetRoomId}/${this.selectedUser}/permissions`,
                formData,
                {
                    headers: { 'Content-Type': 'multipart/form-data' },
                }
                );
                alert('Permissions updated!');
                this.setUserPermsPopup = false;
            } catch (e) {
                alert('Failed to update permissions');
            }
        },
        updateGhostPosition(event) {
            const clientX = event.touches ? event.touches[0].clientX : event.clientX;
            const clientY = event.touches ? event.touches[0].clientY : event.clientY;
            this.ghostX = clientX + 10;
            this.ghostY = clientY + 10;
        },
        handleRoomClick(roomId) {
            if (!this.isReordering && !this.isDragging) {
                this.$emit('room-selected', roomId);
            }
        },
        async handleWsMessage(event) {
            const data = event.detail;
            if (data.type === 'room_edit') {
                if (data.serverId === this.selectedServerId) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                    this.fetchRooms(this.selectedServerId);
                }
            }
        },
        async openSetUserPermsPopup(roomId) {
            this.targetRoomId = roomId;
            this.setUserPermsPopup = true;
            this.selectedUser = null;
            this.userRoomPerms = {
                invite: false,
                read: false,
                write: false,
                manage: false,
                upload: false
            };
            try {
                const res = await axios.get(`${this.fastApiUrl}/servers/${this.selectedServerId}/users`, {
                });
                this.userList = res.data;
            } catch (e) {
                this.userList = [];
                alert('Failed to fetch users:', e);
            }
            this.hideContextMenu();
        },
    }
};
</script>

<style scoped>
.room-list {
    width: 240px;
    min-width: 240px;
    background-color: #2f3136;
    overflow-y: auto;
    height: 100vh;
    /* position: absolute; */
    /* left: 5.5em; */
    /* top: 0; */
}
.room-list ul {
    list-style-type: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
}
.room-list li {
    display: flex;
    align-items: center;
    position: relative;
    padding: 10px;
    border-bottom: 1px solid #444;
    cursor: pointer;
    user-select: none;
}
.room-list li .room-position {
    width: 2em;
    text-align: right;
    margin-right: 0.5em;
    color: #aaa;
    font-weight: bold;
}
.drag-handle {
    margin-left: auto;
    background: none;
    border: none;
    cursor: grab;
    padding: 0 0.5em;
    display: flex;
    align-items: center;
}
.dragging {
    background: #36393f !important;
    opacity: 0.7;
}
.room-list li[draggable="true"] {
    cursor: grab;
}
.room-list li:hover {
    background-color: #3a3c40;
}
.reorder-button {
    background: none;
    border: none;
    color: white;
    cursor: pointer;
    font-size: 1.2em;
    margin-left: 10px;
}
.reorder-controls {
    display: flex;
    justify-content: space-between;
    padding: 10px;
    background-color: #2f3136;
}
.reorder-controls button {
    background-color: #5865f2;
    color: white;
    border: none;
    padding: 5px 10px;
    border-radius: 3px;
    cursor: pointer;
}
.reorder-controls button:hover {
    background-color: #4752c4;
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
.popup-edit-room {
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
.popup-edit-room h3 {
    margin: 0 0 10px;
}
.popup-edit-room form {
    display: flex;
    flex-direction: column;
}
.ghost-room {
    position: fixed;
    pointer-events: none;
    z-index: 9999;
    opacity: 0.7;
    background: #23272a;
    color: #fff;
    border: 1px solid #7289da;
    border-radius: 6px;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    min-width: 120px;
    font-size: 1em;
    /* transition: transform 0.18s cubic-bezier(.4,2,.6,1), top 0.08s, left 0.08s; */
}
.ghost-room .room-position {
    width: 2em;
    text-align: right;
    margin-right: 0.5em;
    color: #aaa;
    font-weight: bold;
}
.drop-target {
    background: rgba(67, 181, 129, 0.25) !important;
    border: 2px solid #43b581 !important;
}
.room-list-ul.room-move-move {
    transition: transform 0.18s cubic-bezier(.4,2,.6,1);
}
.room-list-item {
    transition: background 0.15s, border 0.15s;
}
.drop-target {
    background: rgba(67, 181, 129, 0.25) !important;
    border: 2px solid #43b581 !important;
    min-height: 38px;
    transition: background 0.15s, border 0.15s;
}
.drop-zone-end {
    background: #23272a;
    border: 2px dashed #aaa;
    color: #aaa;
    min-height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-style: italic;
    margin: 4px 0 0 0;
    border-radius: 6px;
    opacity: 0.85;
}

@media (prefers-color-scheme: light) {
    .room-list,
    .popup-edit-room,
    .context-menu {
        background: #fff !important;
        color: #23272a !important;
        border-color: #cfd8dc !important;
    }
    .room-list li,
    .room-list li:hover {
        background: #f7fafd !important;
        color: #23272a !important;
    }
    .context-menu button {
        color: #23272a !important;
    }
    .context-menu button:hover {
        background: #e0e4fa !important;
        color: #5865f2 !important;
    }
    .ghost-room {
        background: #fff;
        color: #23272a;
        border: 1px solid #7289da;
    }
    .drop-target {
        background: rgba(67, 181, 129, 0.12) !important;
        border: 2px solid #43b581 !important;
    }
    .drop-zone-end {
        background: #f7fafd;
        color: #aaa;
        border-color: #cfd8dc;
    }
}
</style>