const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getApiAddress: () => ipcRenderer.invoke('get-api-address')
});