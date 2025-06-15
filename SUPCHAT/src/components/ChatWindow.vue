<template>
    <div class="chat-window" :style="windowStyle">
        <div class="room-header">
            <div class="room-title">{{ roomName || 'Room' }}</div>
            <div class="room-description">{{ roomDescription }}</div>
        </div>
        <div class="messages" v-if="canRead" ref="messages">
            <div
            v-for="(message, idx) in messages"
            :key="message.id"
            class="message-row"
            :class="{
                'editing-message': editingMessage && editingMessage.id === message.id,
                'highlighted-message': highlightedMessageId === message.id
            }"
            :data-message-id="message.id"
            @contextmenu.prevent="showContextMenu($event, message)"
            @mouseenter="message.isHovered = true"
            @mouseleave="message.isHovered = false"
            >
            <template v-if="idx === 0 || messages[idx - 1].userId !== message.userId">
                <div class="avatar-block">
                    <img
                    v-if="users[message.userId]?.profile_picture"
                    :src="users[message.userId].profile_picture"
                    alt="pfp"
                    class="pfp"
                    />
                    <strong class="username">
                        {{ users[message.userId]?.username || message.userId || 'Loading...' }}:
                    </strong>
                </div>
                <span
                class="message-text with-offset"
                v-html="formatMessageText(message.text)"
                ></span>
            </template>
            <template v-else>
                <span class="message-text with-offset" v-html="formatMessageText(message.text)"></span>
            </template>
            <div v-if="message.attachments && message.attachments.length" class="attachments with-offset">
                <div
                v-for="(file, idx) in message.attachments"
                :key="idx"
                class="attachment"
                @mouseenter="hoveredAttachment = `${message.id}_${idx}`"
                @mouseleave="hoveredAttachment = null"
                style="position: relative;"
                >
                <template v-if="file.content_type && file.content_type.startsWith('image/')">
                    <img
                    :src="`${fastApiUrl}/uploads/${message.userId}/${file.filepath.split('/').pop()}`"
                    class="attachment-img"
                    @click="openImagePopup(`${fastApiUrl}/uploads/${message.userId}/${file.filepath.split('/').pop()}`)"
                    style="cursor: zoom-in;"
                    />
                </template>
                <div v-else>
                    <button
                    class="attachment-btn"
                    @click="downloadAttachment(`${fastApiUrl}/uploads/${message.userId}/${file.filepath.split('/').pop()}`)"
                    >
                    📎 {{ file.filename }}
                </button>
            </div>
            <!-- <button
            v-if="(message.userId === userId || canManage) && hoveredAttachment === `${message.id}_${idx}`"
            class="delete-attachment-btn"
            @click="deleteAttachment(message, file)"
            style="position: absolute; top: 4px; right: 4px; background: #ff5555; color: white; border: none; border-radius: 50%; width: 24px; height: 24px; cursor: pointer;"
            title="Delete attachment"
            >🗑️</button> -->
        </div>
    </div>
    <div class="reactions">
        <span
        v-for="reaction in message.reactionList || []"
        :key="reaction.emoji"
        class="reaction"
        :class="{ reacted: reaction.users && reaction.users.includes(userId) }"
        @click="toggleReaction(message, reaction.emoji)"
        >
        {{ reaction.emoji }} {{ reaction.users.length }}
    </span>
    <button
    class="add-reaction-btn"
    v-if="(message.reactionList && message.reactionList.some(r => r.users && r.users.length > 0)) || message.isHovered"
    @click="showReactionPicker(message)"
    >➕</button>
</div>
<div v-if="message.showReactionPicker" class="reaction-picker">
    <span v-for="emoji in emojiList" :key="emoji" @click="addReaction(message, emoji)">{{ emoji }}</span>
</div>
</div>
<div ref="bottomAnchor" style="height: 1px; margin: 0; padding: 0;"></div>
</div>
<!-- <button
class="scrollBottom"
v-if="!isAtBottom"
@click="scrollToBottom"
>↓</button> -->
<button
class="scrollBottom"
@click="scrollToBottom"
>↓</button>
<div class="input-area">
    <div class="attachment-section">
        <button
        class="attachment-btn"
        @click="$refs.fileInput.click()"
        :disabled="!canWrite"
        title="Attach files"
        >📎</button>
        <input
        type="file"
        multiple
        ref="fileInput"
        @change="handleFileChange"
        :disabled="!canWrite"
        style="display: none;"
        accept="image/*,application/pdf,application/zip,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain"
        />
        <div v-if="selectedFiles.length" class="attachment-count">
            {{ selectedFiles.length }} file{{ selectedFiles.length > 1 ? 's' : '' }} selected
        </div>
    </div>
    <textarea
    ref="messageInput"
    v-if="canWrite"
    v-model="newMessage"
    @keydown="handleMessageInputKeydown"
    :placeholder="editingMessage ? 'Edit your message...' : 'Type a message...'"
    class="message-input"
    rows="1"
    @input="autoResize"
    />
    <textarea
    v-else
    disabled
    placeholder="You do not have permission to write in this room."
    class="message-input"
    rows="1"
    />
    <button
    v-if="!editingMessage"
    @click="sendMessage"
    :disabled="!canSend"
    class="send-btn"
    >Send</button>
    <button
    v-else
    @click="submitEditMessage"
    :disabled="newMessage == ''"
    class="edit-btn"
    >Edit</button>
    <button
    v-if="editingMessage"
    @click="cancelEdit"
    class="cancel-btn"
    >Cancel</button>
</div>
</div>

<teleport to="body">
    <div
    v-if="contextMenu.visible"
    class="context-menu"
    :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
    <button @click="copyMessage">Copy message</button>
    <!-- <f>{{ contextMenu.message }} / {{ contextMenu.message.userId }} === {{ userId }}</f> -->
    <button
    v-if="contextMenu.message && contextMenu.message.userId === userId"
    @click="editMessage"
    >Edit message</button>
    <button
    v-if="contextMenu.message && (contextMenu.message.userId === userId || canManage)"
    @click="deleteMessageFromMenu"
    >Delete message</button>
</div>
</teleport>
<div
v-if="mentionActive"
class="mention-suggestions"
>
<div
v-for="(suggestion, idx) in mentionSuggestions"
:key="suggestion.id"
:class="{ active: idx === mentionIndex }"
@mousedown.prevent="mentionIndex = idx; selectMention();"
>
<span v-if="mentionType === 'user'">@{{ suggestion.username }}</span>
<span v-else>#{{ suggestion.roomName }}</span>
</div>
</div>

<div v-if="showSearch" style="width: 50em;">
    <div
    v-if="showSearch"
    class="chat-search-bar"
    >
    <input
    v-model="searchQuery"
    @input="searchMessages"
    ref="searchInput"
    class="chat-search-input"
    placeholder="Search messages or @username..."
    @keydown.esc="closeSearch"
    />
    <button @click="closeSearch" class="close-search-btn">✕</button>
</div>
<div v-if="showSearch && searchResults.length" class="search-results">
    <div
    v-for="msg in searchResults"
    :key="msg.id"
    class="search-result"
    @click="scrollToAndHighlight(msg.id)"
    style="cursor: pointer;"
    >
    <span class="search-result-user">@{{ users[msg.userId]?.username || msg.userId }}</span>:
    <span v-html="formatMessageText(msg.text)"></span>
    <div v-if="msg.attachments && msg.attachments.length" class="search-attachments">
        <div
        v-for="(file, idx) in msg.attachments"
        :key="idx"
        class="search-attachment"
        >
        <template v-if="file.content_type && file.content_type.startsWith('image/')">
            <img
            :src="`${fastApiUrl}/uploads/${msg.userId}/${file.filepath.split('/').pop()}`"
            class="search-attachment-img"
            @click="openImagePopup(`${fastApiUrl}/uploads/${msg.userId}/${file.filepath.split('/').pop()}`)"
            style="cursor: zoom-in;"
            />
        </template>
        <div v-else>
            <button
            class="search-attachment-btn"
            @click="downloadAttachment(`${fastApiUrl}/uploads/${msg.userId}/${file.filepath.split('/').pop()}`)"
            >
            📎 {{ file.filename }}
        </button>
    </div>
</div>
</div>
</div>
</div>
</div>
</template>

<script>
import axios from 'axios';
import { inject } from 'vue';

export default {
    name: 'ChatWindow',
    props: {
        fastApiUrl: {
            type: String,
            default: 'http://127.0.0.1:8000'
        },
        serverId: { type: String, required: true },
        roomId: { type: String, required: true },
        userId: { type: String, required: true },
        selectedServerInfo: { type: Object, required: false, default: null },
        selectedRoomId: { type: String, required: false, default: null },
        windowStyle: { type: Object, default: () => ({}) }
    },
    data() {
        return {
            messages: [],
            newMessage: '',
            canRead: false,
            canWrite: false,
            canManage: false,
            userProfilePicture: null,
            users: {},
            contextMenu: {
                visible: false,
                x: 0,
                y: 0,
                message: null
            },
            wsRef: null,
            ws: null,
            editingMessage: null,
            roomName: '',
            roomDescription: '',
            ignoreNextWsMessage: false,
            selectedFiles: [], 
            hoveredAttachment: null, 
            emojiList: ['😀', '😂', '😍', '😢', '😡', '👍', '👎', '🎉', '❤️', '💔', '👀'],
            isAtBottom: true,
            mentionSuggestions: [],
            mentionType: null, 
            mentionQuery: '',
            mentionActive: false,
            mentionIndex: 0,
            usersList: [], 
            roomsList: [], 
            showSearch: false,
            searchQuery: '',
            searchResults: [],
            searchIndex: 0,
            highlightedMessageId: null,
        };
    },
    async created() {
        await this.fetchUserPermissions();
        await this.fetchMessages();
        await this.fetchUsersAndRooms(); 
    },
    setup(props, { expose }) {
        const ws = inject('ws');
        expose({ ws });
        return { ws };
    },
    mounted() {
        if (this.ws && this.ws.value) {
            this.ws = this.ws.value;
        }
        window.addEventListener('ws-message', this.handleWsMessage);
        window.addEventListener('keydown', this.handleGlobalKeydown);
        const messagesEl = this.$refs.messages;
        if (messagesEl) {
            this._boundCheckIfAtBottom = this.checkIfAtBottom.bind(this);
            messagesEl.addEventListener('scroll', this._boundCheckIfAtBottom);
            this.checkIfAtBottom();
        }
    },
    beforeUnmount() {
        window.removeEventListener('ws-message', this.handleWsMessage);
        window.removeEventListener('keydown', this.handleGlobalKeydown);
        const messagesEl = this.$refs.messages;
        if (messagesEl && this._boundCheckIfAtBottom) {
            messagesEl.removeEventListener('scroll', this._boundCheckIfAtBottom);
        }
    },
    watch: {
        newMessage(newVal) {
            console.log('New message:', newVal);
            if (!newVal) {
                this.mentionActive = false;
                return;
            }
            const lastChar = newVal.slice(-1);
            if (lastChar === '@') {
                this.mentionType = 'user';
                this.mentionActive = true;
                this.mentionSuggestions = this.usersList;
                this.mentionIndex = 0;
            } else if (lastChar === '#') {
                this.mentionType = 'room';
                this.mentionActive = true;
                this.mentionSuggestions = this.roomsList;
                this.mentionIndex = 0;
            } else if (this.mentionActive && lastChar === ' ') {
                this.mentionActive = false;
            }
        },
        roomId: {
            immediate: true,
            handler() {
                this.fetchUserPermissions();
                this.fetchMessages();
                this.fetchRoomInfo();
                this.fetchUsersAndRooms();
            }
        },
        serverId: {
            immediate: true,
            handler() {
                this.fetchUserPermissions();
                this.fetchMessages();
                this.fetchRoomInfo();
                this.fetchUsersAndRooms();
            }
        }
    },
    computed: {
        fileError() {
            if (this.selectedFiles.length > 10) return "You can attach up to 10 files.";
            if (this.selectedFiles.some(f => f.size > 10 * 1024 * 1024)) return "Each file must be ≤ 10MB.";
            return "";
        },
        textError() {
            return this.newMessage.length > 10000 ? "Message too long (max 10,000 characters)." : "";
        },
        canSend() {
            return (
            this.canWrite &&
            !this.fileError &&
            !this.textError &&
            (this.newMessage.trim() !== "" || this.selectedFiles.length > 0)
            );
        }
    },
    methods: {
        handleEnterKey() {
            console.log('Enter key pressed');
            if(!this.mentionActive){
                this.editingMessage ? this.submitEditMessage() : this.sendMessage()
            } else {
                this.selectMention()
            }
        },
        async fetchUserPermissions() {
            try {
                const response = await axios.get(
                `${this.fastApiUrl}/servers/${this.serverId}/${this.roomId}/permissions`
                );
                const perms = response.data;
                this.canRead = !!perms.read || !!perms.superuser;
                this.canWrite = !!perms.write || !!perms.superuser;
                this.canManage = !!perms.manage || !!perms.superuser;
            } catch (error) {
                console.error('Failed to fetch user permissions:', error);
                this.canRead = false;
                this.canWrite = false;
                this.canManage = false;
            }
        },
        async fetchMessages() {
            try {
                const response = await axios.get(`${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}`);
                const messages = response.data;
                await this.fetchUsersForMessages(messages);
                this.messages = messages;
                this.scrollToBottom();
            } catch (error) {
                console.error('Failed to fetch messages:', error);
            }
        },
        async sendMessage() {
            if (this.newMessage.trim() === '' && this.selectedFiles == []) return;
            try {
                const formData = new FormData();
                formData.append('text', this.newMessage ?? '');
                this.selectedFiles.forEach(file => formData.append('attachments', file));
                
                const response = await axios.post(
                    `${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}`,
                    formData,
                    {
                        headers: {
                            'Content-Type': 'multipart/form-data'
                        }
                    }
                );
                if (this.selectedFiles.length == 0) {
                    this.messages.push({
                        id: response.data.id,
                        userId: this.userId,
                        text: this.newMessage,
                        attachments: response.data.attachments || [],
                    });
                    // Ensure user info is present for the sender
                    await this.fetchUsersForMessages([{ userId: this.userId }]);
                }
                this.newMessage = '';
                if (this.$refs.fileInput) {
                    this.$refs.fileInput.value = '';
                }
                if (this.ws && this.ws.readyState === 1) {
                    if (this.selectedFiles.length == 0) {
                        this.ignoreNextWsMessage = true; 
                    }
                    setTimeout(() => {
                        this.ws.send(JSON.stringify({
                            serverId: this.serverId,
                            roomId: this.roomId,
                            type: 'message',
                        }));
                    }, 1000);
                }
                this.selectedFiles = []; // Clear selected files
                this.scrollToBottom();   // Scroll after sending
            } catch (error) {
                console.error('Failed to send message:', error);
            }
        },
        async submitEditMessage() {
            if (!this.editingMessage || this.newMessage.trim() === '') return;
            try {
                await axios.put(
                `${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}/${this.editingMessage.id}`,
                { text: this.newMessage }
                );
                this.editingMessage = null;
                this.newMessage = '';
                if (this.ws && this.ws.readyState === 1) {
                    this.ws.send(JSON.stringify({
                        serverId: this.serverId,
                        roomId: this.roomId,
                        type: 'message',
                    }));
                }
            } catch (error) {
                console.error('Failed to edit message:', error);
            }
        },
        cancelEdit() {
            this.editingMessage = null;
            this.newMessage = '';
        },
        async deleteMessage(messageId) {
            try {
                await axios.delete(`${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}/${messageId}`);
                this.messages = this.messages.filter(message => message.id !== messageId);
            } catch (error) {
                console.error('Failed to delete message:', error);
            }
        },
        async fetchUsersForMessages(messages) {
            const uniqueUserIds = [...new Set(messages.map(m => m.userId).filter(Boolean))];
            for (const userId of uniqueUserIds) {
                if (!this.users[userId]) {
                    try {
                        const userRes = await axios.get(`${this.fastApiUrl}/users/${userId}`);
                        this.users[userId] = {
                            username: userRes.data.username,
                            profile_picture: null
                        };
                        try {
                            const pfpRes = await axios.get(`${this.fastApiUrl}/users/${userId}/profile_picture`, { responseType: 'blob' });
                            const url = URL.createObjectURL(pfpRes.data);
                            this.users[userId].profile_picture = url;
                        } catch (e) {}
                    } catch (e) {
                        this.users[userId] = { username: 'Unknown', profile_picture: null };
                    }
                }
            }
        },
        selectRoom(roomId) {
            this.$emit('room-selected', roomId);
        },
        showContextMenu(event, message) {
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
            this.contextMenu.message = message;
            document.addEventListener('click', this.hideContextMenu);
        },
        hideContextMenu() {
            this.contextMenu.visible = false;
            this.contextMenu.message = null;
            document.removeEventListener('click', this.hideContextMenu);
        },
        copyMessage() {
            if (this.contextMenu.message) {
                navigator.clipboard.writeText(this.contextMenu.message.text);
                this.hideContextMenu();
            }
        },
        editMessage() {
            if (this.contextMenu.message) {
                this.editingMessage = this.contextMenu.message;
                this.newMessage = this.contextMenu.message.text;
                this.hideContextMenu();
            }
        },
        deleteMessageFromMenu() {
            if (this.contextMenu.message) {
                this.deleteMessage(this.contextMenu.message.id);
                if (this.ws && this.ws.readyState === 1) {
                    this.ws.send(JSON.stringify({
                        serverId: this.serverId,
                        roomId: this.roomId,
                        type: 'message',
                    }));
                }
                this.hideContextMenu();
            }
        },
        async handleWsMessage(event) {
            const data = event.detail;
            if (data.type === 'message') {
                if (data.serverId === this.serverId && data.roomId === this.roomId) {
                    if (this.ignoreNextWsMessage) {
                        this.ignoreNextWsMessage = false;
                        return;
                    }
                    setTimeout(async () => {
                        await this.fetchMessages();
                    }, 500);
                }
            }
        },
        async fetchRoomInfo() {
            try {
                const res = await axios.get(`${this.fastApiUrl}/rooms/${this.serverId}/${this.roomId}`);
                this.roomName = res.data.roomName || res.data.room_name || '';
                this.roomDescription = res.data.roomDescription || res.data.room_description || '';
            } catch (e) {
                this.roomName = '';
                this.roomDescription = '';
            }
        },
        handleFileChange(event) {
            const files = Array.from(event.target.files);
            this.selectedFiles = files;
        },
        async downloadAttachment(url) {
            try {
                const response = await axios.get(url, { responseType: 'blob' });
                const blob = new Blob([response.data]);
                const link = document.createElement('a');
                link.href = window.URL.createObjectURL(blob);
                link.download = url.split('/').pop();
                link.click();
                window.URL.revokeObjectURL(link.href);
            } catch (error) {
                console.error('Failed to download attachment:', error);
            }
        },
        openImagePopup(imageUrl) {
            window.open(imageUrl, '_blank');
        },
        deleteAttachment(message, file) {
            const confirmed = confirm(`Are you sure you want to delete this attachment: ${file.filename}?`);
            if (confirmed) {
                const attachmentIndex = message.attachments.findIndex(att => att.filename === file.filename);
                if (attachmentIndex !== -1) {
                    message.attachments.splice(attachmentIndex, 1);
                    console.log(`Deleting attachment: ${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}/${message.id}/attachments/${file.filename}`);
                    axios.delete(`${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}/${message.id}/attachments/${file.filename}`)
                    .then(() => {
                        console.log('Attachment deleted successfully');
                        this.ws.send(JSON.stringify({
                            serverId: this.serverId,
                            roomId: this.roomId,
                            type: 'message',
                        }));
                    })
                    .catch(error => {
                        console.error('Failed to delete attachment:', error);
                    });
                }
            }
        },
        showReactionPicker(message) {
            this.messages.forEach(m => m.showReactionPicker = false);
            message.showReactionPicker = true;
        },
        addReaction(message, emoji) {
            message.showReactionPicker = false;
            this.toggleReaction(message, emoji);
        },
        async toggleReaction(message, emoji) {
            try {
                await axios.post(
                `${this.fastApiUrl}/messages/${this.serverId}/${this.roomId}/${message.id}/reactions`,
                new URLSearchParams({ emoji })
                );
                setTimeout(() => {
                    this.fetchMessages();
                }, 1000);
            } catch (e) {
                alert('Failed to react to message.');
            }
        },
        scrollToBottom() {
            this.$nextTick(() => {
                const anchor = this.$refs.bottomAnchor;
                if (anchor && anchor.scrollIntoView) {
                    anchor.scrollIntoView({ behavior: 'auto' });
                }
            });
        },
        checkIfAtBottom() {
            const messagesEl = this.$refs.messages;
            if (messagesEl) {
                const threshold = 10;
                this.isAtBottom =
                messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < threshold;
            }
        },
        async fetchUsersAndRooms() {
            const usersRes = await axios.get(`${this.fastApiUrl}/servers/${this.serverId}/users`);
            console.log(usersRes.data);
            this.usersList = usersRes.data;
            const roomsRes = await axios.get(`${this.fastApiUrl}/rooms/${this.serverId}`);
            this.roomsList = roomsRes.data;
        },
        // onInput(e) {
        //     const value = e.target.value;
        //     const cursor = e.target.selectionStart;
        //     const beforeCursor = value.slice(0, cursor);
        //     const mentionMatch = /(?:^|\s)([@#])([\w\d_-]*)$/.exec(beforeCursor);
        
        //     if (mentionMatch) {
        //         this.mentionType = mentionMatch[1] === '@' ? 'user' : 'room';
        //         this.mentionQuery = mentionMatch[2].toLowerCase();
        //         this.mentionActive = true;
        //         this.mentionIndex = 0;
        //         if (this.mentionType === 'user') {
        //             this.mentionSuggestions = this.usersList.filter(u =>
        //                 u.username.toLowerCase().startsWith(this.mentionQuery)
        //             );
        //         } else {
        //             this.mentionSuggestions = this.roomsList.filter(r =>
        //                 r.roomName.toLowerCase().startsWith(this.mentionQuery)
        //             );
        //         }
        //     } else {
        //         this.mentionActive = false;
        //     }
        // },
        moveMention(dir) {
            if (!this.mentionActive) return;
            const len = this.mentionSuggestions.length;
            this.mentionIndex = (this.mentionIndex + dir + len) % len;
        },
        selectMention() {
            if (!this.mentionActive || !this.mentionSuggestions.length) return;
            const mention = this.mentionSuggestions[this.mentionIndex];
            let insertText = '';
            console.log(mention);
            if (this.mentionType === 'user') {
                insertText = `<@${mention.userId}>`;
            } else {
                insertText = `<#${mention.roomId}>`;
            }
            const input = this.$refs.messageInput;
            const value = input.value;
            const cursor = input.selectionStart;
            const beforeCursor = value.slice(0, cursor);
            const afterCursor = value.slice(cursor);
            const mentionMatch = /(?:^|\s)([@#])([\w\d_-]*)$/.exec(beforeCursor);
            if (mentionMatch) {
                const start = mentionMatch.index + mentionMatch[0].lastIndexOf(mentionMatch[1]);
                const newValue =
                value.slice(0, start) +
                insertText +
                afterCursor;
                this.newMessage = newValue;
                this.$nextTick(() => {
                    input.selectionStart = input.selectionEnd = start + insertText.length + 1;
                });
            }
            this.mentionActive = false;
        },
        formatMessageText(text) {
            text = text.replace(/<@([a-zA-Z0-9_-]+)>/g, (match, userId) => {
                let username = this.users[userId]?.username;
                if (!username && this.usersList && Array.isArray(this.usersList)) {
                    const userObj = this.usersList.find(u => u.id === userId || u.userId === userId);
                    username = userObj?.username;
                }
                return username ? `<span class="mention">@${username}</span>` : match;
            });
            text = text.replace(/<#([a-zA-Z0-9_-]+)>/g, (match, roomId) => {
                let roomName = null;
                if (this.roomsList && Array.isArray(this.roomsList)) {
                    const roomObj = this.roomsList.find(r => r.id === roomId || r.roomId === roomId);
                    roomName = roomObj?.roomName;
                }
                return roomName ? `<span class="mention">#${roomName}</span>` : match;
            });
            if (this.showSearch && this.searchQuery) {
                const query = this.searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`(${query})`, 'gi');
                text = text.replace(regex, '<span class="search-highlight">$1</span>');
            }
            return text;
        },
        autoResize(event) {
            const textarea = event.target;
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight - 7 + 'px';
        },
        async searchMessages() {
            if (!this.searchQuery) {
                this.searchResults = [];
                return;
            }
            let url = `${this.fastApiUrl}/search/${this.serverId}/${this.roomId}?q=${encodeURIComponent(this.searchQuery)}`;
            try {
                const response = await axios.get(url, {
                });
                this.searchResults = response.data;
            } catch (error) {
                this.searchResults = [];
            }
        },
        scrollToSearchResult() {
            if (!this.searchResults.length) return;
            const idx = this.searchResults[this.searchIndex].idx;
            this.$nextTick(() => {
                const messageEls = this.$el.querySelectorAll('.message-row');
                if (messageEls[idx]) {
                    messageEls[idx].scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        },
        nextSearchResult() {
            if (!this.searchResults.length) return;
            this.searchIndex = (this.searchIndex + 1) % this.searchResults.length;
            this.scrollToSearchResult();
        },
        prevSearchResult() {
            if (!this.searchResults.length) return;
            this.searchIndex = (this.searchIndex - 1 + this.searchResults.length) % this.searchResults.length;
            this.scrollToSearchResult();
        },
        closeSearch() {
            this.showSearch = false;
            this.searchQuery = '';
            this.searchResults = [];
            this.searchIndex = 0;
        },
        openSearch() {
            this.showSearch = true;
            this.$nextTick(() => {
                this.$refs.searchInput?.focus();
            });
        },
        handleGlobalKeydown(e) {
            if (e.ctrlKey && e.key === 'f') {
                e.preventDefault();
                this.openSearch();
            }
        },
        scrollToAndHighlight(messageId) {
            this.showSearch = false;
            this.highlightedMessageId = messageId;
            
            const tryScroll = (retries = 10) => {
                this.$nextTick(() => {
                    const messagesEl = this.$refs.messages;
                    if (!messagesEl) return;
                    const messageEl = messagesEl.querySelector(`[data-message-id="${messageId}"]`);
                    if (messageEl) {
                        messageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    } else if (retries > 0) {
                        setTimeout(() => tryScroll(retries - 1), 100);
                    }
                });
            };
            tryScroll();
            
            setTimeout(() => {
                this.highlightedMessageId = null;
            }, 2500);
        },
        handleMessageInputKeydown(e) {
            if (e.key === 'Enter') {
                if (e.shiftKey) {
                    this.handleEnterKey();
                    e.preventDefault();
                } else {
                    this.$nextTick(() => this.autoResize({ target: e.target }));
                }
            } else if (e.key === 'ArrowDown') {
                this.moveMention(1);
                e.preventDefault();
            } else if (e.key === 'ArrowUp') {
                this.moveMention(-1);
                e.preventDefault();
            }
        },
    }
};
</script>

<style scoped>
.chat-window {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    width: 100%;
}
.room-header {
    padding: 16px 20px 8px 20px;
    background: #23272a;
    border-bottom: 1px solid #222;
}
.room-title {
    font-size: 1.3em;
    font-weight: bold;
    color: #fff;
}
.room-description {
    font-size: 0.95em;
    color: #b9bbbe;
    margin-top: 2px;
}
.messages {
    flex: 1 1 0%;
    overflow-y: auto;
    padding: 10px 10px 0 10px;
    display: flex;
    flex-direction: column;
    min-height: 0;
}
.input-area {
    display: flex;
    align-items: flex-end;
    padding: 10px;
    background-color: #2f3136;
    gap: 10px;
    position: relative;
}
.attachment-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-right: 8px;
    position: relative;
}
.attachment-btn {
    background: #5865f2;
    color: #fff;
    border: none;
    border-radius: 50%;
    width: 36px;
    height: 36px;
    font-size: 1.3em;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    margin-bottom: 2px;
    transition: background 0.2s;
}
.attachment-btn:disabled {
    background: #444;
    cursor: not-allowed;
}
.attachment-btn:hover:not(:disabled) {
    background: #4752c4;
}
.attachment-count {
    font-size: 0.85em;
    color: #b9bbbe;
    margin-top: 2px;
    text-align: center;
    min-width: 60px;
}
.input-area input {
    flex: 1;
    padding: 5px;
    margin-right: 10px;
}
.input-area button {
    padding: 5px 10px;
}
.avatar-block {
    display: flex;
    align-items: center;
    margin-bottom: 2px;
}
.pfp {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    margin-right: 10px;
    vertical-align: middle;
}
.username {
    font-weight: bold;
    color: #fff;
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
.message-row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    margin-bottom: 2px;
    border: 3px solid transparent;
    transition: border-color 0.2s, background 0.2s;
    width: 95%;
}
.editing-message {
    color: white;
    border-radius: 5px;
    background: #6c47ff7c;
    border: 3px solid #7856ff;
}
.message-row:hover {
    background: #23213a;
    border-radius: 5px;
}
.editing-message:hover {
    background: #3a375f;
    border: 3px solid #4b35a0;
}
.avatar-block {
    display: flex;
    align-items: center;
    margin-bottom: 2px;
}
.pfp {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    margin-right: 10px;
    vertical-align: middle;
}
.username {
    font-weight: bold;
    color: #fff;
}
.message-text {
    display: inline-block;
    word-break: break-word;
}
.with-offset {
    margin-left: 50px;
}
.attachments {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
}

.attachment {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    max-width: 200px;
    word-break: break-all;
    /* background: #23213a; */
    /* border-radius: 6px; */
    /* padding: 4px; */
}

.attachment-btn {
    background: none;
    border: none;
    color: #7289da;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
    font: inherit;
    display: block;
    width: 100%;
    text-align: left;
    word-break: break-all;
    white-space: normal;
}
.attachment-img {
    max-width: 180px;
    max-height: 180px;
    border-radius: 6px;
    border: 1px solid #444;
}
.attachment a {
    color: #7289da;
    text-decoration: underline;
    word-break: break-all;
}
.error {
    color: #ff5555;
    margin-top: 4px;
    font-size: 0.95em;
}
.delete-attachment-btn {
    position: absolute;
    top: 4px;
    right: 4px;
    background: #ff5555;
    color: white;
    border: none;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    cursor: pointer;
}
.attachment-btn {
    background: none;
    border: none;
    color: #7289da;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
    font: inherit;
}
.reactions {
    display: flex;
    align-items: center;
    margin-top: 4px;
}
.reaction {
    cursor: pointer;
    margin-right: 5px;
    font-size: 1.2em;
}
.reaction:hover {
    transform: scale(1.2);
}
.reacted {
    animation: bounce 0.3s;
}
.add-reaction-btn {
    background: none;
    border: none;
    color: #7289da;
    cursor: pointer;
    font-size: 1.2em;
    padding: 0;
}
.reaction-picker {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
}
.reaction-picker span {
    cursor: pointer;
    font-size: 1.5em;
}
.reaction-picker span:hover {
    transform: scale(1.2);
}
@keyframes bounce {
    0%,
    100% {
        transform: scale(1);
    }
    50% {
        transform: scale(1.2);
    }
}
.scrollBottom {
    position: fixed;
    bottom: 100px;
    right: 50px;
    background-color: #7289da;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    cursor: pointer;
    z-index: 1000;
}
.mention-suggestions {
    position: absolute;
    background-color: #2f3136;
    border: 1px solid #444;
    border-radius: 5px;
    padding: 8px;
    z-index: 1000;
    width: calc(100% - 20px);
    max-height: 200px;
    overflow-y: auto;
    margin-top: 5px;
    bottom: 5em;
    width: 50%;
    right: 20px;
}
.mention-suggestions div {
    padding: 6px 10px;
    cursor: pointer;
    color: #fff;
}
.mention-suggestions div:hover {
    background-color: #40444b;
}
.active {
    background-color: #40444b !important;
}
.message-input {
    flex: 1 1 auto;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid #444;
    background: #23272a;
    color: #fff;
    font-size: 1em;
    margin-right: 8px;
    outline: none;
    transition: border 0.2s;
    resize: none;
    min-height: 38px;
    max-height: 120px;
    line-height: 1.4;
    overflow-y: auto;
}
.message-input:focus {
    border: 1.5px solid #5865f2;
}
.chat-search-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #23272a;
    padding: 8px 16px;
    border-bottom: 1.5px solid #444;
    position: sticky;
    top: 0;
    z-index: 10;
    padding-top: 6em;
}
.chat-search-input {
    flex: 1;
    padding: 6px 10px;
    border-radius: 4px;
    border: 1px solid #444;
    background: #18191c;
    color: #fff;
    font-size: 1em;
}
.close-search-btn {
    background: none;
    border: none;
    color: #fff;
    font-size: 1.2em;
    cursor: pointer;
}
.search-count {
    color: #b9bbbe;
    font-size: 0.95em;
    margin: 0 8px;
}
.search-highlight {
    background: #ffe066;
    color: #23272a;
    border-radius: 2px;
    padding: 0 2px;
}
.search-results {
    background: #23272a;
    border-top: 1px solid #444;
    /* max-height: 300px; */
    overflow-y: auto;
    padding: 8px 16px;
    height: 35em;
}
.search-result {
    padding: 6px 0;
    border-bottom: 1px solid #333;
    color: #fff;
}
.search-result-user {
    color: #3b82f6;
    font-weight: bold;
}
.search-attachments {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
}
.search-attachment {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    max-width: 200px;
    word-break: break-all;
}
.search-attachment-btn {
    background: none;
    border: none;
    color: #3b82f6;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
    font: inherit;
    display: block;
    width: 100%;
    text-align: left;
    word-break: break-all;
    white-space: normal;
}
.search-attachment-img {
    max-width: 180px;
    max-height: 180px;
    border-radius: 6px;
    border: 1px solid #444;
}
.highlighted-message {
    background: #ffe066 !important;
    transition: background 0.5s;
}
</style>
<style>
.mention {
    background: #3b82f6;
    color: #fff;
    border-radius: 4px;
    padding: 0 4px;
    margin: 0 1px;
    font-weight: bold;
}
@media (prefers-color-scheme: light) {
    .chat-window,
    .room-header,
    .messages,
    .input-area,
    .mention-suggestions,
    .chat-search-bar,
    .search-results {
        background: #fff !important;
        color: #23272a !important;
        border-color: #cfd8dc !important;
    }
    .room-header {
        background: #e0e4fa !important;
        border-bottom: 1px solid #cfd8dc !important;
    }
    .room-title,
    .username {
        color: #23272a !important;
    }
    .room-description {
        color: #555 !important;
    }
    .message-row:hover {
        background: #f7fafd !important;
    }
    .editing-message {
        background: #e0e4fa !important;
        border: 3px solid #5865f2 !important;
        color: #23272a !important;
    }
    .message-input {
        background: #f7fafd !important;
        color: #23272a !important;
        border: 1px solid #cfd8dc !important;
    }
    .message-input:focus {
        border: 1.5px solid #5865f2 !important;
    }
    .attachment-btn,
    .add-reaction-btn {
        color: #5865f2 !important;
        background: #e0e4fa !important;
    }
    .attachment-btn:hover:not(:disabled) {
        background: #cfd8dc !important;
    }
    .attachment-img,
    .search-attachment-img {
        border: 1px solid #cfd8dc !important;
        background: #fff !important;
    }
    .context-menu {
        background: #fff !important;
        color: #23272a !important;
        border: 1px solid #cfd8dc !important;
    }
    .context-menu button {
        color: #23272a !important;
    }
    .context-menu button:hover {
        background: #e0e4fa !important;
        color: #5865f2 !important;
    }
    .mention-suggestions {
        background: #fff !important;
        color: #23272a !important;
        border: 1px solid #cfd8dc !important;
    }
    .mention-suggestions div,
    .mention-suggestions div:hover,
    .active {
        color: #23272a !important;
        background: #e0e4fa !important;
    }
    .search-result {
        color: #23272a !important;
        border-bottom: 1px solid #cfd8dc !important;
    }
    .search-result-user {
        color: #3b82f6 !important;
    }
    .search-highlight {
        background: #ffe066 !important;
        color: #23272a !important;
    }
    .highlighted-message {
        background: #ffe066 !important;
        color: #23272a !important;
    }
}
</style>