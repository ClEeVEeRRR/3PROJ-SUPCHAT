<template>
  <div class="user-profile-edit">
    <h2>Edit Profile</h2>
    <form @submit.prevent="saveProfile" class="profile-form-row">
      <div class="profile-fields">
        <label>
          Username:
          <input v-model="form.username" type="text" required />
        </label>
        <label>
          Email:
          <input v-model="form.email" type="email" required />
        </label>
        <label>
          Description:
          <textarea v-model="form.description" />
        </label>
        <div>
          <button type="submit">Save</button>
          <button type="button" @click="$emit('close')">Cancel</button>
          <button type="button" @click="downloadUserData" class="rgpd-btn">Download My Data</button>
          <div v-if="message" class="message">{{ message }}</div>
        </div>
      </div>
      <div class="profile-cropper">
        Profile Picture:
        <PfpCropper
        v-model="profilePicFile"
        :defaultPfpUrl="previewPfpUrl"
        />
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';
import PfpCropper from './PfpCropper.vue';

const props = defineProps({
  fastApiUrl: {
    type: String,
    default: 'http://127.0.0.1:8000'
  },
  userId: String,
});

const form = ref({
  username: '',
  email: '',
  description: '',
});
const message = ref('');
const profilePicFile = ref(null);
const previewPfpUrl = ref('');

onMounted(async () => {
  try {
    const res = await axios.get(`${props.fastApiUrl}/users/${props.userId}`);
    form.value.username = res.data.username;
    form.value.email = res.data.email;
    form.value.description = res.data.description || '';
    try {
      const pfpRes = await axios.get(`${props.fastApiUrl}/users/${props.userId}/profile_picture`, { responseType: 'blob' });
      previewPfpUrl.value = URL.createObjectURL(pfpRes.data);
    } catch {
      previewPfpUrl.value = '';
    }
  } catch {
    message.value = 'Failed to load profile';
  }
});

async function saveProfile() {
  message.value = '';
  try {
    await axios.put(`${props.fastApiUrl}/users/${props.userId}`, {
      username: form.value.username,
      email: form.value.email,
      description: form.value.description,
    });
    
    if (profilePicFile.value) {
      const formData = new FormData();
      formData.append('profile_picture', profilePicFile.value);
      await axios.put(`${props.fastApiUrl}/users/${props.userId}/profile_picture`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    }
    
    message.value = 'Profile updated!';
  } catch {
    message.value = 'Failed to update profile';
  }
}

async function downloadUserData() {
  try {
    const res = await axios.get(`${props.fastApiUrl}/users/${props.userId}`);
    let profilePictureBase64 = null;
    try {
      const pfpRes = await axios.get(`${props.fastApiUrl}/users/${props.userId}/profile_picture`, { responseType: 'blob' });
      const blob = pfpRes.data;
      profilePictureBase64 = await new Promise(resolve => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
      });
    } catch {}
    const userData = { ...res.data, profile_picture_base64: profilePictureBase64 };
    const blob = new Blob([JSON.stringify(userData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'my_data.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    message.value = 'Failed to download data';
  }
}
</script>

<style scoped>
.user-profile-edit {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #23272a;
  color: #fff;
  padding: 2em;
  border-radius: 10px;
  z-index: 10001;
  min-width: 420px;
  max-height: 90%;
}
.profile-form-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 2em;
}
.profile-fields {
  flex: 1 1 220px;
  min-width: 220px;
}
.profile-cropper {
  min-width: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.user-profile-edit label {
  display: block;
  margin-bottom: 1em;
}
.user-profile-edit input,
.user-profile-edit textarea {
  width: 100%;
  margin-top: 0.3em;
  padding: 0.5em;
  border-radius: 4px;
  border: 1px solid #444;
  background: #18191c;
  color: #fff;
}
.user-profile-edit button {
  margin-right: 1em;
  margin-top: 1em;
}
.message {
  margin-top: 1em;
  color: #4caf50;
}
.rgpd-btn {
  margin-top: 1em;
  background: #7289da;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 0.5em 1.2em;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}
.rgpd-btn:hover {
  background: #5b6eae;
}
@media (prefers-color-scheme: light) {
  .user-profile-edit {
    background: #fff !important;
    color: #23272a !important;
    border: 1px solid #cfd8dc;
  }
  .profile-cropper {
    background: #fff;
  }
  .user-profile-edit input,
  .user-profile-edit textarea {
    background: #f7fafd;
    color: #23272a;
    border: 1px solid #cfd8dc;
  }
  .user-profile-edit button,
  .rgpd-btn {
    background: #5865f2;
    color: #fff;
  }
  .rgpd-btn:hover {
    background: #4752c4;
  }
}
</style>