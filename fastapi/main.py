import base64
from datetime import datetime
import hashlib
from typing import Union
from typing import List
from typing import Optional
from fastapi import Body, FastAPI, HTTPException, Form, File, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import os
from PIL import Image
import io
from fastapi.responses import FileResponse, RedirectResponse
from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from websocket import websocket_endpoint
from fastapi.middleware.cors import CORSMiddleware
from websocket_manager import ConnectionManager
from fastapi import Query

import service

security = HTTPBasic()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

class Message(BaseModel):
    id: Optional[str] = None
    text: str
    originalText: Optional[list] = []
    userId: Optional[str] = None
    location: Optional[str] = None
    reactionList: Optional[list] = []
    creation_date: Optional[datetime] = None
    edit_date: Optional[datetime] = None
    deleted: Optional[bool] = False
    attachments: Optional[list] = []

class User(BaseModel):
    username: str
    password: str
    email: str
    description: str
    userId: str
    creation_date: datetime
    permissions: object
    profile_picture: str

def generate_message_id(serverid: str, roomid: str, userid: str) -> str:
    timestamp = datetime.now().isoformat()

    unique_string = f"{timestamp}-{serverid}-{roomid}-{userid}"

    unique_id = hashlib.sha256(unique_string.encode()).hexdigest()

    return unique_id

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            await manager.broadcast({
                "serverId": data.get("serverId"),
                "roomId": data.get("roomId"),
                "type": data.get("type"),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/swagger")
def swagger_ui():
    return RedirectResponse(url="/docs")

@app.get("/captcha")
def get_captcha():
    try:
        return service.get_captcha_choices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Messages

# get messages from room
@app.get("/messages/{serverid}/{roomid}")
def get_messages_from_room(
    serverid: str,
    roomid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    
    username = credentials.username
    password = credentials.password
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

    uid = service.login(encoded_credentials)

    try:
        return service.getMessages(serverid, roomid, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# search messages
@app.get("/search/{serverid}/{roomid}")
def search_messages(
    serverid: str,
    roomid: str,
    q: str = "",
    credentials: HTTPBasicCredentials = Depends(security)
):
    username = credentials.username
    password = credentials.password
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    uid = service.login(encoded_credentials)

    location = f"{serverid}{roomid}"
    try:
        if q.startswith("@"):
            username_query = q[1:]
            return service.search_messages_by_username(location, username_query, uid)
        else:
            return service.search_messages_by_text(location, q, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# send message
@app.post("/messages/{serverid}/{roomid}")
async def send_message(
    serverid: str,
    roomid: str,
    text: str = Form(..., min_length=0),
    attachments: List[UploadFile] = File([]),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)
        msgid = generate_message_id(serverid, roomid, uid)

        if len(text) > 10000:
            raise HTTPException(status_code=400, detail="Message text too long (max 1000 characters)")
        if len(text) == 0 and not attachments:
            raise HTTPException(status_code=400, detail="Message text cannot be empty if no attachments are provided")
        if len(attachments) > 10:
            raise HTTPException(status_code=400, detail="Too many attachments (max 10)")
        for file in attachments:
            contents = await file.read()
            if len(contents) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Attachment too large (max 10MB)")
            file.file.seek(0)

        attachment_infos = []
        if attachments:
            user_dir = os.path.join("uploads", uid)
            os.makedirs(user_dir, exist_ok=True)
            for file in attachments[:10]:
                contents = await file.read()
                filename = f"{msgid}_{file.filename}"
                filepath = os.path.join(user_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(contents)
                attachment_infos.append({
                    "filename": file.filename,
                    "filepath": filepath,
                    "content_type": file.content_type
                })

        msg = Message(
            id=msgid,
            text=text,
            originalText=[text],
            userId=uid,
            location=serverid + roomid,
            reactionList=[],
            creation_date=datetime.now(),
            edit_date=datetime.now(),
            deleted=False,
            attachments=attachment_infos
        )
        return service.sendMessage(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get file attachments
@app.get("/uploads/{user_id}/{filename}")
def get_attachment(user_id: str, filename: str):
    filepath = os.path.join("uploads", user_id, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)

# edit message
@app.put("/messages/{serverid}/{roomid}/{message_id}")
def edit_message(
    serverid: str,
    roomid: str,
    message: Message,
    message_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        msg = Message(
            id=message_id,
            text=message.text,
            originalText=[message.text],
            userId=uid,
            location=serverid + roomid,
            reactionList=[],
            creation_date=datetime.now(),
            edit_date=datetime.now(),
            deleted=False
        )
        service.editMessage(msg, uid)
        return {"status": "Message sent", "serverid": serverid, "roomid": roomid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# delete message
@app.delete("/messages/{serverid}/{roomid}/{message_id}")
def delete_message(
    serverid: str,
    roomid: str,
    message_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        service.deleteMessage(message_id, uid, serverid, roomid)
        return {"status": "Message deleted", "serverid": serverid, "roomid": roomid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete attachment
@app.delete("/messages/{serverid}/{roomid}/{message_id}/attachments/{filename}")
def delete_attachment(
    serverid: str,
    roomid: str,
    message_id: str,
    filename: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        user_id = service.login(encoded_credentials)

        return service.delete_attachment_from_message(message_id, filename, user_id)
    except Exception as e:
        raise HTTPException(status_code=403, detail=str(e))

# Add reaction to message
@app.post("/messages/{serverid}/{roomid}/{message_id}/reactions")
def react_to_message(
    serverid: str,
    roomid: str,
    message_id: str,
    emoji: str = Form(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        user_id = service.login(encoded_credentials)
        return service.react_to_message(message_id, emoji, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Users

# login
@app.post("/login")
def login(
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        print(username, password)
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)
        return {"status": "Login successful", "uid": uid}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# create user
@app.post("/users")
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    description: str = Form(...),
    permissions: str = Form(...),
    profile_picture: UploadFile = File(...),
    captcha_username: str = Form(...),
    captcha_message: str = Form(...)
):
    try:
        if not service.check_captcha_answer(captcha_username, captcha_message):
            raise HTTPException(status_code=400, detail="Captcha failed. Please try again.")

        userId = service.createUserId()
        if not userId:
            raise HTTPException(status_code=500, detail="Failed to create user ID")

        user = User(
            username=username,
            password=password,
            email=email,
            description=description,
            creation_date=datetime.now(),
            permissions=permissions,
            userId=userId,
            profile_picture=f"{userId}.png"
        )
        
        os.makedirs("uploads", exist_ok=True)
        
        file_path = f"uploads/{userId}.png"
        image = Image.open(io.BytesIO(await profile_picture.read()))
        image.save(file_path, format="PNG", quality=85, optimize=True)
        
        while os.path.getsize(file_path) > 2 * 1024 * 1024:
            image = Image.open(file_path)
            image.save(file_path, format="PNG", quality=75, optimize=True)
        
        service.registerUser(user)
        return {"status": "User registered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# change profile picture
@app.put("/users/{user_id}/profile_picture")
async def change_profile_picture(
    user_id: str,
    profile_picture: UploadFile = File(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    username = credentials.username
    password = credentials.password
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    return await service.changePfp(encoded_credentials, user_id, profile_picture)

# Change password
@app.put("/users/password")
def change_password(
    new_password: str = Form(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        service.changePassword(new_password, uid)
        return {"status": "Password changed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Edit user
@app.put("/users/{user_id}")
def edit_user(
    user_id: str,
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        service.editUser(user_id, username, password, email, description, uid)
        return {"status": "User edited"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get self user
@app.get("/users/me")
def get_self_user(
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        user = service.getUserById(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get all users
@app.get("/users")
def get_all_users(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        uid = service.login(encoded_credentials)
        user = service.getUserById(uid)
        if not user["permissions"].get("superuser", False):
            raise HTTPException(status_code=403, detail="Not allowed")
        return service.getAllUsers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get user by id
@app.get("/users/{user_id}")
def get_user_by_id(user_id: str):
    try:
        user = service.getUserById(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# make superuser
@app.post("/users/{target_id}/make_superuser")
def make_superuser(
    target_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        result = service.makeSuperuser(target_id, encoded_credentials)
        return {"status": "Success", "message": result["message"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get user pfp
@app.get("/users/{user_id}/profile_picture")
def get_profile_picture(user_id: str):
    try:
        return service.downloadPfp(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# delete user
@app.delete("/users/{user_id}/delete")
def delete_user(
    user_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.deleteUser(user_id, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# confirm delete user
@app.delete("/users/{user_id}/confirm")
def confirm_delete_user(
    user_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.confirmDeleteUser(user_id, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Kick user from server
@app.delete("/servers/{server_id}/users/{user_id}/kick")
def kick_user_from_server(
    server_id: str,
    user_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        admin_id = service.login(encoded_credentials)
        return service.kickUserFromServer(server_id, user_id, admin_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Servers

# get server by id
@app.get("/servers/{server_id}")
def get_server_by_id(server_id: str):
    try:
        server = service.getServerById(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        return server
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get server picture
@app.get("/servers/{server_id}/picture")
def get_server_picture(server_id: str):
    try:
        return service.downloadServerPfp(server_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# create server
@app.post("/servers")
async def create_server(
    server_name: str = Form(...),
    server_description: str = Form(...),
    is_public: bool = Form(...),
    server_image: UploadFile = File(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        server_id = await service.createServer(server_name, server_description, is_public, server_image, uid)
        return {"status": "Server created", "server_id": server_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# list servers
@app.get("/servers")
def list_servers(
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        servers = service.listServers(uid)
        return servers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# List users in server
@app.get("/servers/{server_id}/users")
def list_users_in_server(
    server_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        users = service.listUsersInServer(server_id, uid)
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# edit server
@app.put("/servers/{server_id}")
async def edit_server(
    server_id: str,
    server_name: Optional[str] = Form(None),
    server_description: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(None),
    server_image: Optional[UploadFile] = File(None),
    default_permissions: Optional[str] = Form(None),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        print(server_name, "\n")
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        await service.editServer(server_id, server_name, server_description, is_public, server_image, uid, default_permissions)
        return {"status": "Server edited"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# delete server
@app.delete("/servers/{server_id}/delete")
def delete_server(
    server_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.deleteServer(server_id, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# confirm delete server
@app.delete("/servers/{server_id}/confirm")
def confirm_delete_server(
    server_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.confirmDeleteServer(server_id, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Rooms

# create room
@app.post("/rooms/{serverid}")
def create_room(
    serverid: str,
    room_name: str = Form(...),
    room_description: str = Form(...),
    everyone_can_invite: bool = Form(...),
    everyone_can_see: bool = Form(...),
    everyone_can_write: bool = Form(...),
    everyone_can_manage: bool = Form(...),
    everyone_can_upload: bool = Form(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.createRoom(serverid, room_name, room_description, uid, everyone_can_invite, everyone_can_see, everyone_can_write, everyone_can_manage, everyone_can_upload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# list rooms
@app.get("/rooms/{serverid}")
def list_rooms(
    serverid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.listRooms(serverid, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get room by id
@app.get("/rooms/{serverid}/{roomid}")
def get_room_by_id(
    serverid: str,
    roomid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        room = service.getRoomById(serverid, roomid, uid)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        return room
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# edit room
@app.put("/rooms/{serverid}/{roomid}")
def edit_room(
    serverid: str,
    roomid: str,
    room_name: Optional[str] = Form(None),
    room_description: Optional[str] = Form(None),
    everyone_can_invite: Optional[bool] = Form(None),
    everyone_can_see: Optional[bool] = Form(None),
    everyone_can_write: Optional[bool] = Form(None),
    everyone_can_manage: Optional[bool] = Form(None),
    everyone_can_upload: Optional[bool] = Form(None),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.editRoom(serverid, roomid, uid, room_name, room_description, everyone_can_invite, everyone_can_see, everyone_can_write, everyone_can_manage, everyone_can_upload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# delete room
@app.delete("/rooms/{serverid}/{roomid}/delete")
def delete_room(
    serverid: str,
    roomid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.deleteRoom(serverid, roomid, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# confirm delete room
@app.delete("/rooms/{serverid}/{roomid}/confirm")
def confirm_delete_room(
    serverid: str,
    roomid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.confirmDeleteRoom(serverid, roomid, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Roles

# create role
@app.post("/roles/{serverid}")
def create_role(
    serverid: str,
    role_name: str = Form(...),
    permissions: object = Form(...),
    role_color: str = Form(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        uid = service.login(encoded_credentials)

        return service.createRole(serverid, role_name, permissions, role_color, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get role
@app.get("/roles/{serverid}/{roleid}")
def get_role(
    serverid: str,
    roleid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        role = service.getRole(serverid, roleid, uid)
        return {"role": role}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get roles from server
@app.get("/roles/{serverid}")
def get_roles_from_server(
    serverid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        roles = service.getRolesFromServer(serverid, uid)
        return {"roles": roles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# edit role
@app.put("/roles/{serverid}/{roleid}")
def edit_role(
    serverid: str,
    roleid: str,
    role_name: Optional[str] = Form(None),
    permissions: Optional[object] = Form(None),
    role_color: Optional[str] = Form(None),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.editRole(serverid, roleid, role_name, permissions, role_color, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# delete role
@app.delete("/roles/{serverid}/{roleid}/delete")
def delete_role(
    serverid: str,
    roleid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.deleteRole(serverid, roleid, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# confirm delete role
@app.delete("/roles/{serverid}/{roleid}/confirm")
def confirm_delete_role(
    serverid: str,
    roleid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.confirmDeleteRole(serverid, roleid, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Others

# add server permissions to user
@app.put("/servers/{serverid}/{userid}/permissions")
def add_server_permissions_to_user(
    serverid: str,
    userid: str,
    permissions: object = Form(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        raise HTTPException(status_code=501, detail="Disabled for now")
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.addServerPermissionsToUser(serverid, userid, permissions, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# add room permissions to user
@app.put("/rooms/{serverid}/{roomid}/{userid}/permissions")
def add_room_permissions_to_user(
    serverid: str,
    roomid: str,
    userid: str,
    permissions: object = Form(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.addRoomPermissionsToUser(serverid, roomid, userid, permissions, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# change room order in server
@app.put("/servers/{serverid}/rooms")
def change_room_order_in_server(
    serverid: str,
    room_order: list = Body(...),
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.changeRoomOrderInServer(serverid, room_order, uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get user permissions in server and room
@app.get("/servers/{serverid}/{roomid}/permissions")
def get_user_perms(
    serverid: str,
    roomid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        uid = service.login(encoded_credentials)

        return service.checkPerms(uid, serverid, roomid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Invite users to server
@app.post("/servers/{server_id}/invite")
async def invite_to_server(
    server_id: str,
    target_email: str = Form(""),
    duration_minutes: int = Form(1440),
    one_time: bool = Form(True),
    send_email: bool = Form(False),
    credentials: HTTPBasicCredentials = Depends(security)
):
    username = credentials.username
    password = credentials.password
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

    user_id = service.login(encoded_credentials)
    perms = service.checkPerms(user_id, server_id, "0")
    if not perms.get("invite", False):
        raise HTTPException(status_code=403, detail="You do not have permission to invite users to this server.")

    # invite_url = "https://www.youtube.com/watch?v=SJuojhiyzlI"
    if send_email:
        try:
            service.send_invite_email(target_email, "message", invite_url)
            return {"status": "email sent"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        invite_id = service.create_invite(server_id, user_id, duration_minutes, one_time)
        invite_url = f"<appAddress>/invite/{invite_id}"
        return {"invite_url": invite_url}

@app.get("/invite/{invite_id}")
def consume_invite(invite_id: str, credentials: HTTPBasicCredentials = Depends(security)):
    try:
        invite = service.validate_invite(invite_id)
        return invite
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/invite/{invite_id}/accept")
def accept_invite(
    invite_id: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    try:
        username = credentials.username
        password = credentials.password
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        user_id = service.login(encoded_credentials)

        invite = service.validate_invite(invite_id)
        server_id = invite["serverId"]

        server = service.getServerById(server_id)
        if "members" not in server:
            server["members"] = []
        if user_id not in server["members"]:
            server["members"].append(user_id)
            service.es.index(index="servers", id=server_id, body=server)

        if invite.get("oneTime", False):
            service.use_invite(invite_id, user_id)

        return {"status": "success", "message": "You have joined the server."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
