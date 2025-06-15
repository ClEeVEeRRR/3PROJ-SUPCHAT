<template>
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
                :width="displayWidth"
                :height="displayHeight"
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
</template>

<script>
import pfp1 from '../assets/img/examplepfp/pfp1.png';
import pfp2 from '../assets/img/examplepfp/pfp2.png';
import pfp3 from '../assets/img/examplepfp/pfp3.png';

export default {
    name: 'PfpCropper',
    props: {
        modelValue: File,
        defaultPfpUrl: {
            type: String,
            default: () => [pfp1, pfp2, pfp3][Math.floor(Math.random() * 3)]
        }
    },
    emits: ['update:modelValue'],
    data() {
        return {
            selectedPfpUrl: null,
            croppedPfpUrl: null,
            showCropper: false,
            cropImage: null,
            cropRect: { x: 50, y: 50, size: 150, dragging: false, resizing: false, resizeCorner: null },
            displayScale: 1,
            imageNaturalWidth: 0,
            imageNaturalHeight: 0,
            maxDisplaySize: 400,
            displayWidth: 220,
            displayHeight: 220,
        };
    },
    methods: {
        onDefaultPfpError(e) {
            e.target.src = pfp1;
        },
        onProfilePicChange(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                this.selectedPfpUrl = evt.target.result;
                const img = new window.Image();
                img.onload = () => {
                    const maxDisplaySize = 220;
                    const scale = Math.min(maxDisplaySize / img.width, maxDisplaySize / img.height, 1);
                    this.displayScale = scale;
                    this.imageNaturalWidth = img.width;
                    this.imageNaturalHeight = img.height;
                    this.displayWidth = Math.round(img.width * scale);
                    this.displayHeight = Math.round(img.height * scale);
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
            ctx.drawImage(
            img,
            0, 0, this.imageNaturalWidth, this.imageNaturalHeight,
            0, 0, this.displayWidth, this.displayHeight
            );
            
            const { x, y, size } = this.cropRect;
            ctx.save();
            ctx.strokeStyle = "#00bfff";
            ctx.lineWidth = 2;
            const scale = this.displayWidth / this.imageNaturalWidth;
            ctx.strokeRect(
            this.cropRect.x * scale,
            this.cropRect.y * scale,
            this.cropRect.size * scale,
            this.cropRect.size * scale
            );
            
            ctx.fillStyle = "#00bfff";
            const handleSize = 8;
            ctx.fillRect(x * this.displayScale - handleSize/2, y * this.displayScale - handleSize/2, handleSize, handleSize);
            ctx.fillRect((x + size) * this.displayScale - handleSize/2, y * this.displayScale - handleSize/2, handleSize, handleSize);
            ctx.fillRect(x * this.displayScale - handleSize/2, (y + size) * this.displayScale - handleSize/2, handleSize, handleSize);
            ctx.fillRect((x + size) * this.displayScale - handleSize/2, (y + size) * this.displayScale - handleSize/2, handleSize, handleSize);
            ctx.restore();
        },
        startCrop(e) {
            const rect = this.$refs.cropCanvas.getBoundingClientRect();
            // Mouse position in canvas coordinates
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            // Convert to image coordinates
            const scale = this.displayWidth / this.imageNaturalWidth;
            const imgX = mouseX / scale;
            const imgY = mouseY / scale;
            
            const { x, y, size } = this.cropRect;
            const handleSize = 10 / scale; 
            
            const corners = [
            { name: 'tl', x: x, y: y },
            { name: 'tr', x: x + size, y: y },
            { name: 'bl', x: x, y: y + size },
            { name: 'br', x: x + size, y: y + size }
            ];
            for (const corner of corners) {
                if (
                Math.abs(imgX - corner.x) < handleSize &&
                Math.abs(imgY - corner.y) < handleSize
                ) {
                    this.cropRect.resizing = true;
                    this.cropRect.resizeCorner = corner.name;
                    return;
                }
            }
            if (
            imgX > x && imgX < x + size &&
            imgY > y && imgY < y + size
            ) {
                this.cropRect.dragging = true;
                this.cropRect.offsetX = imgX - x;
                this.cropRect.offsetY = imgY - y;
            }
        },
        moveCrop(e) {
            if (!this.showCropper) return;
            const rect = this.$refs.cropCanvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            const scale = this.displayWidth / this.imageNaturalWidth;
            const imgX = mouseX / scale;
            const imgY = mouseY / scale;
            const minSize = 40 / scale;
            let { x, y, size, dragging, resizing, resizeCorner, offsetX, offsetY } = this.cropRect;
            
            if (resizing && resizeCorner) {
                let newX = x, newY = y, newSize = size;
                switch (resizeCorner) {
                    case 'tl':
                    newSize = size + (x - imgX);
                    newX = imgX;
                    newY = imgY;
                    break;
                    case 'tr':
                    newSize = size + (imgX - (x + size));
                    newY = imgY;
                    break;
                    case 'bl':
                    newSize = size + (x - imgX);
                    newX = imgX;
                    break;
                    case 'br':
                    newSize = size + (imgX - (x + size));
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
                let newX = imgX - offsetX;
                let newY = imgY - offsetY;
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
                const file = new File([blob], "server_picture.png", { type: "image/png" });
                this.$emit('update:modelValue', file);
            });
            this.showCropper = false;
        },
        cancelCrop() {
            this.showCropper = false;
            this.selectedPfpUrl = null;
        }
    }
};
</script>

<style scoped>
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
    /* max-width: 220px;
    max-height: 220px; */
    width: 100%;
    height: auto;
}
.cropper-canvas-wrapper {
    position: relative;
    margin-bottom: 10px;
}

@media (prefers-color-scheme: light) {
    .pfp-cropper,
    .cropper-controls,
    .cropper-canvas-wrapper {
        background: #fff !important;
        color: #23272a !important;
    }
    .pfp-img {
        border: 2px solid #5865f2;
        background: #fff;
    }
    .cropper-controls canvas {
        background: #fff;
        border: 1px solid #5865f2;
    }
}
</style>