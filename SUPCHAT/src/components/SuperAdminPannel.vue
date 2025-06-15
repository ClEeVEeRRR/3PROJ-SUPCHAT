<template>
  <div class="superadmin-panel">
    <button class="close-superadmin-btn" @click="$emit('close')">✕</button>
    <h2>SuperAdmin Panel</h2>
    <div v-if="loading">Loading users...</div>
    <div v-else>
      <table class="user-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>UserId</th>
            <th>Superuser</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.userId">
            <td>{{ user.username }}</td>
            <td>{{ user.userId }}</td>
            <td>{{ user.permissions?.superuser ? 'Yes' : 'No' }}</td>
            <td>
              <button @click="makeSuperuser(user.userId)" :disabled="user.permissions?.superuser">Make Superuser</button>
              <button @click="editUser(user)">Edit</button>
              <button @click="openConfirmDeleteDialog(user)">Ban (Delete)</button>
              <button @click="openKickDialog(user)">Kick from Server</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="editDialog" class="dialog">
        <h3>Edit User: {{ editUserObj.username }}</h3>
        <label>
          Username: <input v-model="editUserObj.username" />
        </label>
        <label>
          Email: <input v-model="editUserObj.email" />
        </label>
        <label>
          Description: <input v-model="editUserObj.description" />
        </label>
        <button @click="saveUserEdit">Save</button>
        <button @click="editDialog = false">Cancel</button>
      </div>
      <div v-if="kickDialog" class="dialog">
        <h3>Kick {{ kickUserObj.username }} from server</h3>
        <label>
          Server:
          <select v-model="kickServerId">
            <option v-for="srv in kickUserServers" :key="srv.serverId" :value="srv.serverId">
              {{ srv.serverName || srv.serverId }}
            </option>
          </select>
        </label>
        <button @click="kickUserFromServer" :disabled="!kickServerId">Kick</button>
        <button @click="kickDialog = false">Cancel</button>
      </div>
      <div v-if="confirmDeleteDialog" class="dialog">
        <h3>Confirm Ban (Delete) User: {{ confirmDeleteUserObj.username }}</h3>
        <label>
          Type the username to confirm: <input v-model="confirmDeleteInput" />
        </label>
        <button @click="confirmDeleteUser">Confirm Ban (Delete)</button>
        <button @click="confirmDeleteDialog = false">Cancel</button>
      </div>
    </div>
    <div v-if="message" class="message">{{ message }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';

const props = defineProps({
  fastApiUrl: {
    type: String,
    default: 'http://127.0.0.1:8000'
  },
});

const users = ref([]);
const loading = ref(true);
const message = ref('');
const editDialog = ref(false);
const editUserObj = ref({});
const kickDialog = ref(false);
const kickUserObj = ref({});
const kickServerId = ref('');
const confirmDeleteDialog = ref(false);
const confirmDeleteUserObj = ref({});
const confirmDeleteInput = ref('');
const kickUserServers = ref([]);

async function fetchUsers() {
  loading.value = true;
  try {
    const res = await axios.get(props.fastApiUrl + '/users');
    users.value = res.data;
  } catch (e) {
    message.value = 'Failed to load users';
  }
  loading.value = false;
}

async function makeSuperuser(userId) {
  try {
    await axios.post(props.fastApiUrl + `/users/${userId}/make_superuser`);
    message.value = 'User is now superuser';
    setTimeout(fetchUsers, 1500)
  } catch (e) {
    message.value = 'Failed to make superuser';
  }
}

function editUser(user) {
  editUserObj.value = { ...user };
  editDialog.value = true;
}

async function saveUserEdit() {
  try {
    await axios.put(props.fastApiUrl + `/users/${editUserObj.value.userId}`, {
      username: editUserObj.value.username,
      email: editUserObj.value.email,
      description: editUserObj.value.description,
    });
    message.value = 'User updated';
    editDialog.value = false;
    setTimeout(fetchUsers, 1500)
  } catch (e) {
    message.value = 'Failed to update user';
  }
}

function openConfirmDeleteDialog(user) {
  confirmDeleteUserObj.value = user;
  confirmDeleteInput.value = '';
  confirmDeleteDialog.value = true;
}

async function confirmDeleteUser() {
  if (confirmDeleteInput.value !== confirmDeleteUserObj.value.username) {
    message.value = 'Username does not match.';
    return;
  }
  try {
    await axios.delete(props.fastApiUrl + `/users/${confirmDeleteUserObj.value.userId}/delete`);
    await axios.delete(props.fastApiUrl + `/users/${confirmDeleteUserObj.value.userId}/confirm`);
    message.value = 'User deleted.';
    confirmDeleteDialog.value = false;
    setTimeout(fetchUsers, 1500)
  } catch (e) {
    message.value = 'Failed to delete user.';
  }
}

async function openKickDialog(user) {
  kickUserObj.value = user;
  kickDialog.value = true;
  kickServerId.value = '';
  try {
    const res = await axios.get(props.fastApiUrl + '/servers');
    kickUserServers.value = res.data.filter(s => (s.members || []).includes(user.userId));
  } catch (e) {
    kickUserServers.value = [];
  }
}

async function kickUserFromServer() {
  if (!kickServerId.value) return;
  try {
    await axios.delete(props.fastApiUrl + `/servers/${kickServerId.value}/users/${kickUserObj.value.userId}/kick`);
    message.value = 'User kicked from server';
    kickDialog.value = false;
    setTimeout(fetchUsers, 1500)
  } catch (e) {
    message.value = 'Failed to kick user';
  }
}

onMounted(fetchUsers);
</script>

<style scoped>
.superadmin-panel {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  background: rgba(30, 32, 40, 0.98);
  overflow: auto;
}
.user-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1em;
}
.user-table th, .user-table td {
  border: 1px solid #444;
  padding: 8px;
}
.user-table th {
  background: #18191c;
}
.dialog {
  background: #18191c;
  border: 1px solid #444;
  padding: 16px;
  margin: 16px 0;
  border-radius: 8px;
}
.message {
  margin-top: 1em;
  color: #ffe066;
}
button {
  margin-right: 8px;
  background: #5865f2;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 4px 12px;
  cursor: pointer;
}
button:hover {
  background: #4752c4;
}
.close-superadmin-btn {
  position: absolute;
  top: 16px;
  right: 24px;
  background: none;
  border: none;
  color: #fff;
  font-size: 2em;
  cursor: pointer;
  z-index: 10000;
}
@media (prefers-color-scheme: light) {
  .superadmin-panel {
    background: rgba(255,255,255,0.98);
    color: #23272a;
  }
  .user-table th, .user-table td {
    border: 1px solid #cfd8dc;
    color: #23272a;
  }
  .user-table th {
    background: #e0e4fa;
  }
  .dialog {
    background: #fff;
    border: 1px solid #cfd8dc;
    color: #23272a;
  }
  .message {
    color: #5865f2;
  }
  button {
    background: #5865f2;
    color: #fff;
  }
  button:hover {
    background: #4752c4;
  }
  .close-superadmin-btn {
    color: #23272a;
  }
}
</style>