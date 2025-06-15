<template>
    <div class="login-page">
        <form v-if="!isRegister" @submit.prevent="login">
            <input v-model="username" type="text" placeholder="Username" required />
            <input v-model="password" type="password" placeholder="Password" required />
            <label>
                <input type="checkbox" v-model="rememberMe" />
                Remember me
            </label>
            <button type="submit">Login</button>
            <button type="button" @click="showRegister">Register</button>
            <div v-if="displayError" class="error" v-html="displayErrorWithBreaks"></div>
        </form>
        <form v-else @submit.prevent="register">
            <input v-model="registerUsername" type="text" placeholder="Username" required />
            <input v-model="registerPassword" type="password" placeholder="Password" required />
            <input v-model="registerEmail" type="email" placeholder="Email" required />
            <div class="pfp-cropper">
                <div class="pfp-preview">
                    <img
                    :src="croppedPfpUrl || selectedPfpUrl || defaultPfpUrl"
                    alt="Profile Preview"
                    class="pfp-img"
                    @error="onDefaultPfpError"
                    />
                </div>
                <input type="file" accept="image/*" @change="onProfilePicChange" />
                <div v-if="showCropper" class="cropper-controls">
                    <div class="cropper-canvas-wrapper" style="position: relative;">
                        <canvas
                        ref="cropCanvas"
                        :width="cropImage ? cropImage.width : 300"
                        :height="cropImage ? cropImage.height : 300"
                        @mousedown="startCrop"
                        @mousemove="moveCrop"
                        @mouseup="endCrop"
                        @mouseleave="endCrop"
                        style="border: 1px solid #7289da; background: #23272a; cursor: crosshair;"
                        ></canvas>
                    </div>
                    <button type="button" @click="applyCrop">Apply Crop</button>
                    <button type="button" @click="cancelCrop">Cancel</button>
                </div>
            </div>
            <!-- <textarea v-model="registerDescription" placeholder="Description (optional)"></textarea> -->
            <div v-if="captchaChoices.length">
                <div><b>Botfinder captcha:</b> Select the suspicious user/message:</div>
                <div v-for="(choice, idx) in captchaChoices" :key="idx" style="margin-bottom: 4px;">
                    <label>
                        <input type="radio" :value="choice" v-model="selectedCaptcha" />
                        <b>{{ choice.username }}</b>: {{ choice.message }}
                    </label>
                </div>
                <button type="button" @click="fetchCaptcha" style="margin-top: 4px;">Refresh captcha</button>
            </div>
            <button type="submit">Register</button>
            <button type="button" @click="isRegister = false">Back to Login</button>
            <div v-if="registerError" class="error" v-html="registerErrorWithBreaks"></div>
        </form>
    </div>
</template>

<script>
import axios from 'axios';
import pfp1 from '../assets/img/examplepfp/pfp1.png';
import pfp2 from '../assets/img/examplepfp/pfp2.png';
import pfp3 from '../assets/img/examplepfp/pfp3.png';

export default {
    name: 'Login',
    props: {
        fastApiUrl: {
            type: String,
            default: 'http://127.0.0.1:8000'
        },
        error: {
            type: String,
            default: ''
        }
    },
    data() {
        const pfps = [pfp1, pfp2, pfp3];
        const randomPfpIndex = Math.floor(Math.random() * pfps.length);
        return {
            username: '',
            password: '',
            rememberMe: false,
            localError: '',
            isRegister: false,
            registerUsername: '',
            registerPassword: '',
            registerEmail: '',
            registerDescription: '',
            registerProfilePic: null,
            registerError: '',
            captchaChoices: [],
            selectedCaptcha: null,
            selectedPfpUrl: null,
            croppedPfpUrl: null,
            showCropper: false,
            cropSize: 200,
            cropStartX: 0,
            cropStartY: 0,
            cropEndX: 0,
            cropEndY: 0,
            isCropping: false,
            crop: { x: 0, y: 0, dragging: false },
            cropImage: null,
            pfps,
            randomPfpIndex,
            cropCanvasSize: 300,
            cropRect: { x: 50, y: 50, size: 150, dragging: false, resizing: false, resizeCorner: null },
            maxDisplaySize: 400,
            displayScale: 1,
        };
    },
    mounted() {
        this.fetchCaptcha();
    },
    computed: {
        displayError() {
            return this.error || this.localError;
        },
        displayErrorWithBreaks() {
            return String(this.displayError).replace(/\n/g, '<br>');
        },
        registerErrorWithBreaks() {
            return typeof this.registerError === 'string'
            ? this.registerError.replace(/\n/g, '<br>')
            : JSON.stringify(this.registerError);
        },
        defaultPfpUrl() {
            return this.pfps[this.randomPfpIndex];
        }
    },
    methods: {
        onDefaultPfpError(e) {
            e.target.src = `/assets/img/examplepfp/pfp1.png`;
            // e.target.src = `/assets/img/examplepfp/pfp${this.randomPfp}.png`;
        },
        showRegister() {
            if (this.username) this.registerUsername = this.username;
            if (this.password) this.registerPassword = this.password;
            this.isRegister = true;
            this.fetchCaptcha();
        },
        async login() {
            if (!this.username || !this.password) {
                this.localError = 'Username and password required';
                return;
            }
            const credentials = btoa(`${this.username}:${this.password}`);
            try {
                const response = await axios.post(
                `${this.fastApiUrl}/login`,
                {},
                {
                    headers: {
                        'Authorization': `Basic ${credentials}`
                    }
                }
                );
                this.localError = '';
                const uid = response.data.uid;
                if (this.rememberMe) {
                    localStorage.setItem('auth', credentials);
                } else {
                    sessionStorage.setItem('auth', credentials);
                }
                this.$emit('login-success', { credentials, rememberMe: this.rememberMe });
            } catch (err) {
                if (
                err.message &&
                (err.message.includes('Network Error') ||
                err.message.includes('ERR_CONNECTION_REFUSED') ||
                (err.code && err.code === 'ERR_NETWORK'))
                ) {
                    this.localError = 'Could not connect to the server. Please try again later.';
                } else if (err.response && err.response.status === 401) {
                    this.localError = 'Invalid username or password';
                } else {
                    this.localError = 'Something went wrong. Please try again.';
                }
            }
        },
        onProfilePicChange(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                this.selectedPfpUrl = evt.target.result;
                const img = new window.Image();
                img.onload = () => {
                    const scale = Math.min(this.maxDisplaySize / img.width, this.maxDisplaySize / img.height, 1);
                    this.displayScale = scale;
                    this.imageNaturalWidth = img.width;
                    this.imageNaturalHeight = img.height;
                    const size = Math.min(img.width, img.height, 200 / scale);
                    this.cropRect = {
                        x: Math.floor((img.width - size) / 2),
                        y: Math.floor((img.height - size) / 2),
                        size: size,
                        dragging: false,
                        resizing: false,
                        resizeCorner: null
                    };
                    this.showCropper = true;
                    this.$nextTick(this.drawCropper);
                };
                img.src = evt.target.result;
                this.cropImage = img;
            };
            reader.readAsDataURL(file);
        },
        drawCropper() {
            const canvas = this.$refs.cropCanvas;
            const img = this.cropImage;
            if (!canvas || !img) return;
            canvas.width = img.width * this.displayScale;
            canvas.height = img.height * this.displayScale;
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            
            const { x, y, size } = this.cropRect;
            ctx.save();
            ctx.strokeStyle = "#00bfff";
            ctx.lineWidth = 2;
            ctx.strokeRect(x * this.displayScale, y * this.displayScale, size * this.displayScale, size * this.displayScale);
            
            // Draw resize handles (corners)
            ctx.fillStyle = "#00bfff";
            const handleSize = 8;
            ctx.fillRect(x * this.displayScale - handleSize/2, y * this.displayScale - handleSize/2, handleSize, handleSize); // top-left
            ctx.fillRect((x + size) * this.displayScale - handleSize/2, y * this.displayScale - handleSize/2, handleSize, handleSize); // top-right
            ctx.fillRect(x * this.displayScale - handleSize/2, (y + size) * this.displayScale - handleSize/2, handleSize, handleSize); // bottom-left
            ctx.fillRect((x + size) * this.displayScale - handleSize/2, (y + size) * this.displayScale - handleSize/2, handleSize, handleSize); // bottom-right
            ctx.restore();
        },
        startCrop(e) {
            const rect = this.$refs.cropCanvas.getBoundingClientRect();
            const mouseX = (e.clientX - rect.left) / this.displayScale;
            const mouseY = (e.clientY - rect.top) / this.displayScale;
            const { x, y, size } = this.cropRect;
            const handleSize = 10;
            
            const corners = [
            { name: 'tl', x: x, y: y },
            { name: 'tr', x: x + size, y: y },
            { name: 'bl', x: x, y: y + size },
            { name: 'br', x: x + size, y: y + size }
            ];
            for (const corner of corners) {
                if (
                Math.abs(mouseX - corner.x) < handleSize &&
                Math.abs(mouseY - corner.y) < handleSize
                ) {
                    this.cropRect.resizing = true;
                    this.cropRect.resizeCorner = corner.name;
                    return;
                }
            }
            
            if (
            mouseX > x && mouseX < x + size &&
            mouseY > y && mouseY < y + size
            ) {
                this.cropRect.dragging = true;
                this.cropRect.offsetX = mouseX - x;
                this.cropRect.offsetY = mouseY - y;
            }
        },
        moveCrop(e) {
            if (!this.showCropper) return;
            const rect = this.$refs.cropCanvas.getBoundingClientRect();
            const mouseX = (e.clientX - rect.left) / this.displayScale;
            const mouseY = (e.clientY - rect.top) / this.displayScale;
            const minSize = 40 / this.displayScale;
            let { x, y, size, dragging, resizing, resizeCorner, offsetX, offsetY } = this.cropRect;
            
            if (resizing && resizeCorner) {
                let newX = x, newY = y, newSize = size;
                switch (resizeCorner) {
                    case 'tl':
                    newSize = size + (x - mouseX);
                    newX = mouseX;
                    newY = mouseY;
                    break;
                    case 'tr':
                    newSize = size + (mouseX - (x + size));
                    newY = mouseY;
                    break;
                    case 'bl':
                    newSize = size + (x - mouseX);
                    newX = mouseX;
                    break;
                    case 'br':
                    newSize = size + (mouseX - (x + size));
                    break;
                }
                newSize = Math.max(minSize, Math.min(this.imageNaturalWidth - newX, this.imageNaturalHeight - newY, newSize));
                newX = Math.max(0, Math.min(newX, this.imageNaturalWidth - newSize));
                newY = Math.max(0, Math.min(newY, this.imageNaturalHeight - newSize));
                this.cropRect.x = newX;
                this.cropRect.y = newY;
                this.cropRect.size = newSize;
                this.$nextTick(this.drawCropper);
            } else if (dragging) {
                let newX = mouseX - offsetX;
                let newY = mouseY - offsetY;
                newX = Math.max(0, Math.min(newX, this.imageNaturalWidth - size));
                newY = Math.max(0, Math.min(newY, this.imageNaturalHeight - size));
                this.cropRect.x = newX;
                this.cropRect.y = newY;
                this.$nextTick(this.drawCropper);
            }
        },
        endCrop() {
            this.cropRect.dragging = false;
            this.cropRect.resizing = false;
            this.cropRect.resizeCorner = null;
        },
        applyCrop() {
            const { x, y, size } = this.cropRect;
            const img = this.cropImage;
            if (!img) return;
            const canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, x, y, size, size, 0, 0, size, size);
            this.croppedPfpUrl = canvas.toDataURL('image/png');
            fetch(this.croppedPfpUrl)
            .then(res => res.blob())
            .then(blob => {
                this.registerProfilePic = new File([blob], "profile.png", { type: "image/png" });
            });
            this.showCropper = false;
        },
        cancelCrop() {
            this.showCropper = false;
            this.selectedPfpUrl = null;
        },
        async fetchCaptcha() {
            try {
                const res = await axios.get(`${this.fastApiUrl}/captcha`);
                this.captchaChoices = res.data;
                this.selectedCaptcha = null;
            } catch (e) {
                this.captchaChoices = [];
            }
        },
        async register() {
            this.registerError = '';
            if (!this.registerUsername || !this.registerPassword || !this.registerEmail) {
                this.registerError = 'All fields except description are required.';
                return;
            }
            if (!this.selectedCaptcha) {
                this.registerError = "Please select the suspicious user/message.";
                return;
            }
            const formData = new FormData();
            formData.append('username', this.registerUsername);
            formData.append('password', this.registerPassword);
            formData.append('email', this.registerEmail);
            formData.append('permissions', {});
            formData.append('description', this.registerDescription ?? '');
            if (this.registerProfilePic) {
                formData.append('profile_picture', this.registerProfilePic);
            }
            formData.append('captcha_username', this.selectedCaptcha.username);
            formData.append('captcha_message', this.selectedCaptcha.message);
            try {
                await axios.post(`${this.fastApiUrl}/users`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });
                this.isRegister = false;
                this.localError = 'Registration successful! Please log in.';
                this.registerUsername = '';
                this.registerPassword = '';
                this.registerEmail = '';
                this.registerDescription = '';
                this.registerProfilePic = null;
                this.fetchCaptcha();
            } catch (err) {
                if (err.response && err.response.data && err.response.data.detail) {
                    if (typeof err.response.data.detail === 'string' && err.response.data.detail.toLowerCase().includes('captcha')) {
                        this.registerError = 'Captcha incorrect! Please try again.';
                        this.fetchCaptcha();
                    } else if (typeof err.response.data.detail === 'string' && err.response.data.detail.toLowerCase().includes('email')) {
                        this.registerError = 'Email already in use.';
                    } else {
                        this.registerError = err.response.data.detail;
                    }
                } else {
                    this.registerError = 'Registration failed.';
                }
                this.fetchCaptcha();
            }
        }
    }
};
</script>

<style scoped>
body, #app {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #23272a;
    height: fit-content;
}

.login-page {
    max-width: 800px;
    width: 800px;
    margin: 0px auto 0 auto;
    padding: 32px 28px 24px 28px;
    background: #23272a;
    color: #f6f6f6;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35), 0 1.5px 4px rgba(0,0,0,0.18);
    font-family: 'Segoe UI', Arial, sans-serif;
    box-sizing: border-box;
    height: fit-content;
}

form {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

input[type="text"],
input[type="password"],
input[type="email"],
textarea {
    padding: 9px 12px;
    border: 1px solid #444a;
    border-radius: 6px;
    font-size: 1em;
    background: #2c2f33;
    color: #f6f6f6;
    transition: border 0.2s;
}

input[type="text"]:focus,
input[type="password"]:focus,
input[type="email"]:focus,
textarea:focus {
    background: #23272a;
    border-color: #7289da;
    outline: none;
}

label {
    font-size: 0.97em;
    color: #e0e0e0;
    display: flex;
    align-items: center;
    gap: 6px;
}

button[type="submit"],
button[type="button"] {
    padding: 9px 0;
    border: none;
    border-radius: 6px;
    background: #5865f2;
    color: #fff;
    font-weight: 600;
    font-size: 1em;
    cursor: pointer;
    margin-top: 2px;
    transition: background 0.18s;
    width: 100%;
    box-sizing: border-box;
}

button[type="button"] {
    background: #23272a;
    color: #7289da;
    border: 1px solid #7289da;
}

button[type="submit"]:hover {
    background: #4752c4;
}

button[type="button"]:hover {
    background: #36393f;
}

.error {
    color: #ffb3b3;
    background: #2c1a1a;
    border: 1px solid #a33;
    border-radius: 5px;
    padding: 7px 10px;
    margin-top: 4px;
    font-size: 0.97em;
    white-space: pre-line;
}

textarea {
    min-height: 60px;
    resize: vertical;
}

.captcha label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.97em;
}

.captcha {
    margin-bottom: 8px;
}

.pfp-cropper {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 1em;
}
.pfp-preview {
    margin-bottom: 8px;
}
.pfp-img {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #7289da;
    background: #23272a;
}
.cropper-controls {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
}
.cropper-controls canvas {
    border: 1px solid #7289da;
    background: #23272a;
    cursor: crosshair;
    display: block;
}
.cropper-canvas-wrapper {
    position: relative;
    margin-bottom: 10px;
}

@media (max-width: 500px) {
    .login-page {
        max-width: 98vw;
        padding: 18px 4vw;
    }
}

@media (prefers-color-scheme: light) {
    .login-page {
        background: #fff;
        color: #23272a;
        box-shadow: 0 4px 24px rgba(0,0,0,0.10), 0 1.5px 4px rgba(0,0,0,0.07);
    }
    input[type="text"],
    input[type="password"],
    input[type="email"],
    textarea {
        background: #f7fafd;
        color: #23272a;
        border: 1px solid #cfd8dc;
    }
    input[type="text"]:focus,
    input[type="password"]:focus,
    input[type="email"]:focus,
    textarea:focus {
        background: #fff;
        border-color: #5865f2;
    }
    label {
        color: #444;
    }
    button[type="submit"],
    button[type="button"] {
        background: #5865f2;
        color: #fff;
    }
    button[type="button"] {
        background: #e0e4fa;
        color: #5865f2;
        border: none;
    }
    button[type="submit"]:hover {
        background: #4752c4;
    }
    button[type="button"]:hover {
        background: #d1d8fa;
    }
    .error {
        color: #e74c3c;
        background: #fff0f0;
        border: 1px solid #f5c2c7;
    }
}
</style>