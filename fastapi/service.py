from datetime import datetime, timedelta
import os
from elasticsearch import Elasticsearch
from fastapi import UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.responses import FileResponse
import base64
import uuid
import json
from PIL import Image
import io
from dotenv import load_dotenv
import random
from websocket_manager import ConnectionManager
import smtplib
from email.mime.text import MIMEText
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTCHA_PATH = os.path.join(BASE_DIR, "nonconspicuousinfo.json")
load_dotenv()

class User(BaseModel):
    username: str
    password: str
    email: str
    description: str
    creation_date: datetime
    permissions: object
    profile_picture: str
    
class Message(BaseModel):
    id: str
    text: str
    originalText: str
    userId: str
    location: str
    reactionList: list
    creation_date: datetime
    edit_date: datetime
    deleted: bool
    attachments: list = []

def wait_for_elasticsearch(host, timeout=60):
    start = time.time()
    while True:
        try:
            es = Elasticsearch(host)
            if es.ping():
                print("Elasticsearch is ready!")
                return es
        except Exception as e:
            print("Waiting for Elasticsearch...", e)
        if time.time() - start > timeout:
            raise Exception("Timed out waiting for Elasticsearch")
        time.sleep(2)

es = wait_for_elasticsearch(os.environ.get("ELASTICSEARCH_HOST", "http://elasticsearch:9200"))

# es = Elasticsearch(hosts=[os.getenv("ELASTICSEARCH_URL")], basic_auth=(os.getenv("ELASTICSEARCH_USER"), os.getenv("ELASTICSEARCH_PASSWORD")))
# es = Elasticsearch(hosts=[os.getenv("ELASTICSEARCH_URL")])

deletion_window = timedelta(minutes=10)

# Check if indexes exist, if not create them
if not es.indices.exists(index="users"):
    es.indices.create(index="users")
if not es.indices.exists(index="messages"):
    es.indices.create(index="messages")
if not es.indices.exists(index="servers"):
    es.indices.create(index="servers")
if not es.indices.exists(index="rooms"):
    es.indices.create(index="rooms")
if not es.indices.exists(index="roles"):
    es.indices.create(index="roles")

def createUserId():
    while True:
        user_id = str(uuid.uuid4())
        try:
            es.get(index="users", id=user_id)
        except:
            return user_id

def createServerId():
    while True:
        server_id = str(uuid.uuid4())
        try:
            es.get(index="servers", id=server_id)
        except:
            return server_id

def createRoleId():
    while True:
        role_id = str(uuid.uuid4())
        try:
            es.get(index="roles", id=role_id)
        except:
            return role_id

def strip_sensitive_user_fields(user):
    user = dict(user)
    user.pop("password", None)
    # user.pop("email", None)
    # user.pop("permissions", None)
    # user.pop("creation_date", None)
    # user.pop("marked_for_deletion", None)
    # user.pop("deletion_timestamp", None)
    # user.pop("description", None)
    # user.pop("profile_picture", None)
    return user

def translatePermissions(permissions):
    print("permissions: ", permissions)
    sanitized = permissions.replace("'", "\\\"").replace("'", "\"").replace("\\n", "").replace("\r", "").replace("True", "true").replace("False", "false").replace("None", "null")
    print("sanitized: ", sanitized)
    jsonstr = json.loads(sanitized)
    print(jsonstr)
    return jsonstr

def makeSuperuser(targetId: str, credentials: str):
    try:
        user_id = login(credentials)

        user_data = es.get(index="users", id=user_id)["_source"]
        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if not user_data["permissions"].get("superuser", False):
            raise Exception("Only superusers can grant superuser permissions.")

        target_user = es.get(index="users", id=targetId)["_source"]
        if type(target_user["permissions"]) == str:
            target_user["permissions"] = translatePermissions(target_user["permissions"])

        target_user["permissions"]["superuser"] = True

        es.index(index="users", id=targetId, body=target_user)

        return {"status": "Success", "message": f"User {targetId} is now a superuser."}
    except Exception as e:
        raise Exception(f"Failed to make superuser: {str(e)}")

def login(credentials: str):
    try:
        decoded_credentials = base64.b64decode(credentials).decode()
        username, password = decoded_credentials.split(":")

        query = {
            "size": 1000,
            "query": {
                "match": {
                    "username": username
                }
            }
        }
        search_result = es.search(index="users", body=query)

        if search_result["hits"]["total"]["value"] == 0:
            raise Exception("Invalid username or password.")

        user_data = search_result["hits"]["hits"][0]["_source"]

        stored_password = base64.b64decode(user_data["password"]).decode()

        encoded_db_credentials = base64.b64encode(f"{user_data['username']}:{stored_password}".encode()).decode()

        if credentials != encoded_db_credentials:
            raise Exception("Invalid username or password.")

        return user_data['userId']
    except Exception as e:
        raise Exception(f"Failed to login: {str(e)}")

def checkPerms(userId: str, serverid: str, roomId: str):
    try:
        user_data = es.get(index="users", id=userId)["_source"]
        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])

        if user_data["permissions"].get("superuser", False):
            return {
                "read": True,
                "write": True,
                "manage": True,
                "invite": True,
                "upload": True,
                "superuser": True
            }

        server_perms = user_data["permissions"].get(serverid, {})
        if roomId != "0":
            room_perms = user_data["permissions"].get(serverid, {}).get(roomId, {})
        else:
            room_perms = {}

        try:
            server_data = es.get(index="servers", id=serverid)["_source"]
            server_default_perms = server_data.get("default_permissions", {})
        except Exception:
            server_default_perms = {}

        if roomId != "0":
            try:
                room_data = es.get(index="rooms", id=roomId)["_source"]
                room_default_perms = room_data.get("default_permissions", {})
            except Exception:
                room_default_perms = {}
        else:
            room_default_perms = {}

        perms = {}
        for key in ["read", "write", "manage", "invite", "upload"]:
            perms[key] = (
                bool(server_perms.get(key, False)) or
                bool(room_perms.get(key, False)) or
                bool(server_default_perms.get(key, False)) or
                bool(room_default_perms.get(key, False))
            )
        perms["superuser"] = False

        return perms
    except Exception as e:
        raise Exception(f"Failed to find user or permissions: {str(e)}")

def sendMessage(message: Message):
    if not message:
        raise ValueError("No message object received")
    try:
        es.index(index="messages", id=message.id, body=message.dict())
        return {
            "status": "Message sent",
            "userId": message.userId,
            "text": message.text,
            "id": message.id,
            }
    except Exception as e:
        raise Exception(f"Failed to transfer message: {str(e)}")

def editMessage(message: Message, uuid: str):
    if not message:
        raise ValueError("No message object received")
    try:
        message_data = es.get(index="messages", id=message.id)["_source"]

        if message_data["userId"] != uuid:
            raise Exception("You are not the owner of this message.")
        elif message_data["deleted"] == True:
            raise Exception("This message has been deleted.")
        else:
            message_data["text"] = message.text
            message_data["originalText"].append(message.text)
            message_data["edit_date"] = datetime.now()
            es.index(index="messages", id=message.id, body=message_data)
            return {"status": "Message edited"}
    except Exception as e:
        raise Exception(f"Failed to edit message: {str(e)}")

def deleteMessage(message_id: str, uuid: str, server_id: str, room_id: str):
    if not message_id:
        raise ValueError("No message id received")
    try:
        message_data = es.get(index="messages", id=message_id)["_source"]

        perms = checkPerms(uuid, server_id, room_id)

        if message_data["userId"] != uuid and not perms.get("superuser", False) and not perms.get("manage", False):
            raise Exception("You are not the owner of this message.")
        elif message_data["deleted"] == True:
            raise Exception("This message has already been deleted.")
        else:
            for attachment in message_data.get("attachments", []):
                delete_attachment_from_message(message_id, attachment["filename"], uuid)
            message_data["deleted"] = True
            es.index(index="messages", id=message_id, body=message_data)
            return {"status": "Message deleted"}
    except Exception as e:
        raise Exception(f"Failed to delete message: {str(e)}")

def registerUser(user: User):
    if not user:
        raise ValueError("No user object received")
    try:
        query = {
            "size": 1000,
            "query": {
                "bool": {
                    "should": [
                        {"match": {"email": user.email}},
                        {"match": {"username": user.username}}
                    ]
                }
            }
        }
        search_result = es.search(index="users", body=query)
        if search_result["hits"]["total"]["value"] > 0:
            for hit in search_result["hits"]["hits"]:
                if hit["_source"]["email"] == user.email:
                    raise Exception(f"Email {user.email} already exists.")
                if hit["_source"]["username"] == user.username:
                    raise Exception(f"Username {user.username} already used.")

        user.password = base64.b64encode(user.password.encode()).decode()
        user.permissions = {"superuser": False}
        es.index(index="users", id=user.userId, body=user.dict())
        if es.count(index="users")["count"] == 0:
            user.permissions["superuser"] = True
            es.index(index="users", id=user.userId, body=user.dict())
        return {"status": "User registered"}
    except Exception as e:
        raise Exception(f"Failed to register user: {str(e)}")

def deleteUser(user_id: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and user_id != uid:
            raise Exception("Only superusers can delete other users.")

        user_data["marked_for_deletion"] = True
        user_data["deletion_timestamp"] = datetime.now().isoformat()

        es.index(index="users", id=user_id, body=user_data)

        return {"status": f"User marked for deletion. Confirm within the next {str(deletion_window)}."}
    except Exception as e:
        raise Exception(f"Failed to mark user for deletion: {str(e)}")

def confirmDeleteUser(user_id: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and user_id != uid:
            raise Exception("Only superusers can confirm user deletions.")

        target_user_data = es.get(index="users", id=user_id)["_source"]

        if not target_user_data.get("marked_for_deletion", False):
            raise Exception("User is not marked for deletion.")

        deletion_timestamp = datetime.fromisoformat(target_user_data["deletion_timestamp"])
        if datetime.now() > deletion_timestamp + deletion_window:
            raise Exception("Confirmation window has expired. User deletion canceled.")

        es.delete(index="users", id=user_id)

        return {"status": "User successfully deleted."}
    except Exception as e:
        raise Exception(f"Failed to confirm user deletion: {str(e)}")

def downloadPfp(user_id: str):
    try:
        file_path = f"uploads/{user_id}.png"
        if not os.path.exists(file_path):
            raise Exception(f"Profile picture for user ID {user_id} does not exist.")
        return FileResponse(file_path, media_type='image/png', filename=f"{user_id}.png")
    except Exception as e:
        raise Exception(f"Failed to download profile picture: {str(e)}")

async def changePfp(credentials: str, user_id: str, img: UploadFile):
    try:
        issuer_id = login(credentials)
        if not Image:
            raise ValueError("No image object received")
        
        user_data = es.get(index="users", id=issuer_id)["_source"]
        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if issuer_id != user_id and user_data["permissions"].get("superuser", False):
            if user_data["permissions"]["superuser"] == False:
                raise Exception("Only superusers can change profile pictures")
        
        os.makedirs("uploads", exist_ok=True)
        
        file_path = f"uploads/{user_id}.png"
        image = Image.open(io.BytesIO(await img.read()))
        image.save(file_path, format="PNG", quality=85, optimize=True)
        
        while os.path.getsize(file_path) > 2 * 1024 * 1024:
            image = Image.open(file_path)
            image.save(file_path, format="PNG", quality=75, optimize=True)

        return {"status": "Profile picture updated"}
    except Exception as e:
        raise Exception(f"Failed to update profile picture: {str(e)}")

def getMessages(serverid: str, roomid: str, credentials: str):
    try:
        user_id = credentials

        permissions = checkPerms(user_id, serverid, roomid)

        if not permissions["read"] and not permissions["superuser"]:
            raise Exception("User does not have permission to read messages in this room.")

        query = {
            "size": 1000,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"location.keyword": f"{serverid}{roomid}"}},
                        {"term": {"deleted": False}}
                    ]
                }
            },
            "sort": [
                {"creation_date": {"order": "asc"}}
            ]
        }
        search_result = es.search(index="messages", body=query)

        messages = [hit["_source"] for hit in search_result["hits"]["hits"]]
        return messages
    except Exception as e:
        raise Exception(f"Failed to get messages: {str(e)}")

def changePassword(new_password: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        user_data["password"] = base64.b64encode(new_password.encode()).decode()

        es.index(index="users", id=uid, body=user_data)

        return {"status": "Password changed"}
    except Exception as e:
        raise Exception(f"Failed to change password: {str(e)}")

def editUser(user_id: str, username: str, password: str, email: str, description: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and user_id != uid:
            raise Exception("Only superusers can edit users.")

        if username:
            user_data["username"] = username
        if password:
            user_data["password"] = base64.b64encode(password.encode()).decode()
        if email:
            user_data["email"] = email
        if description:
            user_data["description"] = description

        es.index(index="users", id=user_id, body=user_data)

        return {"status": "User edited"}
    except Exception as e:
        raise Exception(f"Failed to edit user: {str(e)}")

def getUserById(user_id: str):
    try:
        user_data = es.get(index="users", id=user_id)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])

        return strip_sensitive_user_fields(user_data)
    except Exception as e:
        raise Exception(f"Failed to get user by ID: {str(e)}")

async def createServer(server_name: str, server_description: str, is_public: bool, server_image: UploadFile, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False:
            raise Exception("Only superusers can create servers.")

        os.makedirs("uploads", exist_ok=True)

        server_id = createServerId()

        file_path = f"uploads/{server_id}.png"
        image = Image.open(io.BytesIO(await server_image.read()))
        image.save(file_path, format="PNG", quality=85, optimize=True)

        while os.path.getsize(file_path) > 2 * 1024 * 1024:
            image = Image.open(file_path)
            image.save(file_path, format="PNG", quality=75, optimize=True)

        server_data = {
            "serverId": server_id,
            "serverName": server_name,
            "serverDescription": server_description,
            "isPublic": is_public,
            "serverImage": file_path,
            "creation_date": datetime.now(),
            "ownerId": uid,
            "rooms": [],
            "marked_for_deletion": False,
            "deletion_timestamp": None,
            "default_permissions": {
                "read": False,
                "write": False,
                "manage": False,
                "invite": False,
                "upload": False
            },
            "members": [],
            "roles": [],
            # "permissions": {
            #     "superuser": True,
            #     server_id: {
            #         "read": True,
            #         "write": True,
            #         "manage": True
            #     }
            # }
        }

        es.index(index="servers", id=server_id, body=server_data)

        return {"id": server_id}
    except Exception as e:
        raise Exception(f"Failed to create server: {str(e)}")

def getServerById(server_id: str):
    try:
        server_data = es.get(index="servers", id=server_id)["_source"]

        # if type(server_data["permissions"]) == str:
        #     server_data["permissions"] = translatePermissions(server_data["permissions"])

        return server_data
    except Exception as e:
        raise Exception(f"Failed to get server by ID: {str(e)}")

async def editServer(server_id: str, server_name: str, server_description: str, is_public: bool, server_image: UploadFile, uid: str, default_permissions: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False:
            raise Exception("Only superusers can edit servers.")

        os.makedirs("uploads", exist_ok=True)

        server_data = es.get(index="servers", id=server_id)["_source"]

        if server_name:
            server_data["serverName"] = server_name
        if server_description:
            server_data["serverDescription"] = server_description
        if is_public is not None:
            server_data["isPublic"] = is_public
        if default_permissions:
            server_data["default_permissions"] = translatePermissions(default_permissions)

        if server_image:
            old_file_path = f"uploads/{server_id}.png"
            if os.path.exists(old_file_path):
                os.remove(old_file_path)

            file_path = f"uploads/{server_id}.png"
            image = Image.open(io.BytesIO(await server_image.read()))
            image.save(file_path, format="PNG", quality=85, optimize=True)

            while os.path.getsize(file_path) > 2 * 1024 * 1024:
                image = Image.open(file_path)
                image.save(file_path, format="PNG", quality=75, optimize=True)

        es.index(index="servers", id=server_id, body=server_data)

        updated_server_data = es.get(index="servers", id=server_id)["_source"]

        return {"status": "Server edited"}
    except Exception as e:
        raise Exception(f"Failed to edit server: {str(e)}")

def deleteServer(server_id: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        # if type(user_data["permissions"]) == str:
        #     user_data["permissions"] = translatePermissions(user_data["permissions"])
        # if user_data["permissions"].get("superuser", False) == False:
        #     raise Exception("Only superusers can delete servers.")

        server_data = es.get(index="servers", id=server_id)["_source"]

        server_data["marked_for_deletion"] = True
        server_data["deletion_timestamp"] = datetime.now().isoformat()

        es.index(index="servers", id=server_id, body=server_data)

        return {"status": f"Server marked for deletion. Confirm within the next {str(deletion_window)}."}
    except Exception as e:
        raise Exception(f"Failed to mark server for deletion: {str(e)}")

def confirmDeleteServer(server_id: str, uid: str):
    try:
        # user_data = es.get(index="users", id=uid)["_source"]

        # if type(user_data["permissions"]) == str:
        #     user_data["permissions"] = translatePermissions(user_data["permissions"])
        # if user_data["permissions"].get("superuser", False) == False:
        #     raise Exception("Only superusers can confirm server deletions.")

        server_data = es.get(index="servers", id=server_id)["_source"]

        if not server_data.get("marked_for_deletion", False):
            raise Exception("Server is not marked for deletion.")

        deletion_timestamp = datetime.fromisoformat(server_data["deletion_timestamp"])
        if datetime.now() > deletion_timestamp + deletion_window:
            raise Exception("Confirmation window has expired. Server deletion canceled.")

        es.delete(index="servers", id=server_id)

        return {"status": "Server successfully deleted."}
    except Exception as e:
        raise Exception(f"Failed to confirm server deletion: {str(e)}")

def createRoom(serverid: str, room_name: str, room_description: str, uid: str, everyone_can_invite: bool, everyone_can_see: bool, everyone_can_write: bool, everyone_can_manage: bool, everyone_can_upload: bool):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False:
            raise Exception("Only superusers can create rooms.")

        room_id = str(uuid.uuid4())

        room_data = {
            "roomId": room_id,
            "roomName": room_name,
            "roomDescription": room_description,
            "serverId": serverid,
            "creation_date": datetime.now(),
            "ownerId": uid,
            "default_permissions": {
                "read": everyone_can_see,
                "write": everyone_can_write,
                "manage": everyone_can_manage,
                "invite": everyone_can_invite,
                "upload": everyone_can_upload
            },
            # "permissions": {
            #     "superuser": True,
            #     serverid: {
            #         "read": True,
            #         "write": True,
            #         "manage": True
            #     }
            # }
        }

        es.index(index="rooms", id=room_id, body=room_data)

        server_data = es.get(index="servers", id=serverid)["_source"]
        server_data["rooms"].append(room_id)
        es.index(index="servers", id=serverid, body=server_data)

        return {"room_id": room_id}
    except Exception as e:
        raise Exception(f"Failed to create room: {str(e)}")

def listRooms(serverid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        query = {
            "size": 1000,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"serverId": serverid}}
                    ]
                }
            }
        }
        search_result = es.search(index="rooms", body=query)
        rooms = []

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        # print("user is looking for perms [[[[[[[[[[[]]]]]]]]]]]")
        # print("user_data['permissions']: ", user_data["permissions"])
        for hit in search_result["hits"]["hits"]:
            room = hit["_source"]
            # print('User permissions: ', user_data["permissions"])
            # print('Room permissions: ', room["default_permissions"])
            # print('User permissions for room: ', user_data["permissions"].get(serverid, {}).get(room["roomId"], {}))
            if (
                "read" in user_data["permissions"].get(serverid, {}).get(room["roomId"], {}) or
                "manage" in user_data["permissions"].get(serverid, {}).get(room["roomId"], {}) or
                room["default_permissions"].get("read", False) or
                room["default_permissions"].get("manage", False)
            ):
                rooms.append(room)

        if user_data["permissions"].get("superuser", False):
            rooms = [hit["_source"] for hit in search_result["hits"]["hits"]]

        return rooms

    except Exception as e:
        raise Exception(f"Failed to list rooms: {str(e)}")

def editRoom(serverid: str, roomid: str, uid: str, room_name: str, room_description: str, everyone_can_invite: bool, everyone_can_see: bool, everyone_can_write: bool, everyone_can_manage: bool, everyone_can_upload: bool):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        room_data = es.get(index="rooms", id=roomid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if not (
            user_data["permissions"].get("superuser", False)
            or "manage" in user_data["permissions"].get(room_data["roomId"], [])
            or room_data["default_permissions"].get("manage", False)
        ):
            raise Exception("You are not allowed to edit rooms.")

        if room_name:
            room_data["roomName"] = room_name
        if room_description:
            room_data["roomDescription"] = room_description
        if everyone_can_invite is not None:
            room_data["default_permissions"]["invite"] = everyone_can_invite
        if everyone_can_see is not None:
            room_data["default_permissions"]["read"] = everyone_can_see
        if everyone_can_write is not None:
            room_data["default_permissions"]["write"] = everyone_can_write
        if everyone_can_manage is not None:
            room_data["default_permissions"]["manage"] = everyone_can_manage
        if everyone_can_upload is not None:
            room_data["default_permissions"]["upload"] = everyone_can_upload

        es.index(index="rooms", id=roomid, body=room_data)

        return {"status": "Room edited"}
    except Exception as e:
        raise Exception(f"Failed to edit room: {str(e)}")

def deleteRoom(serverid: str, roomid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if not (
                user_data["permissions"].get("superuser", False)
                or "manage" in user_data["permissions"].get(room_data["roomId"], [])
                or room_data["default_permissions"].get("manage", False)
            ):
            raise Exception("You are not allowed to delete rooms.")

        room_data = es.get(index="rooms", id=roomid)["_source"]

        room_data["marked_for_deletion"] = True
        room_data["deletion_timestamp"] = datetime.now().isoformat()

        es.index(index="rooms", id=roomid, body=room_data)

        return {"status": f"Room marked for deletion. Confirm within the next {str(deletion_window)}."}
    except Exception as e:
        raise Exception(f"Failed to mark room for deletion: {str(e)}")

def confirmDeleteRoom(serverid: str, roomid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if not (
            user_data["permissions"].get("superuser", False)
            or "manage" in user_data["permissions"].get(room_data["roomId"], [])
            or room_data["default_permissions"].get("manage", False)
        ):
            raise Exception("You are not allowed to confirm room deletions.")

        room_data = es.get(index="rooms", id=roomid)["_source"]

        if not room_data.get("marked_for_deletion", False):
            raise Exception("Room is not marked for deletion.")

        deletion_timestamp = datetime.fromisoformat(room_data["deletion_timestamp"])
        if datetime.now() > deletion_timestamp + deletion_window:
            raise Exception("Confirmation window has expired. Room deletion canceled.")

        es.delete(index="rooms", id=roomid)

        return {"status": "Room successfully deleted."}
    except Exception as e:
        raise Exception(f"Failed to confirm room deletion: {str(e)}")

def createRole(serverid: str, role_name: str, permissions: object, role_color: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}) and server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to create roles.")

        role_id = createRoleId()

        if type(permissions) == str:
            permissions = translatePermissions(permissions)

        role_data = {
            "roleId": role_id,
            "roleName": role_name,
            "serverId": serverid,
            "creation_date": datetime.now(),
            "ownerId": uid,
            "permissions": permissions,
            "roleColor": role_color
        }

        es.index(index="roles", id=role_id, body=role_data)

        server_data = es.get(index="servers", id=serverid)["_source"]
        if "roles" not in server_data:
            server_data["roles"] = []
        server_data["roles"].append(role_id)
        es.index(index="servers", id=serverid, body=server_data)

        return {"role_id": role_id}
    except Exception as e:
        raise Exception(f"Failed to create role: {str(e)}")

def addServerPermissionsToUser(serverid: str, userid: str, permissions: object, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]
        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}).includes("manage") and server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to add server permissions to users.")

        target_user_data = es.get(index="users", id=userid)["_source"]

        if "permissions" not in target_user_data:
            target_user_data["permissions"] = {}
        target_user_data["permissions"][serverid] = permissions

        es.index(index="users", id=userid, body=target_user_data)

        return {"status": "Server permissions added to user"}
    except Exception as e:
        raise Exception(f"Failed to add server permissions to user: {str(e)}")

def addRoomPermissionsToUser(serverid: str, roomid: str, userid: str, permissions: object, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]
        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}) and not server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to add room permissions to users.")

        target_user_data = es.get(index="users", id=userid)["_source"]

        if "permissions" not in target_user_data:
            target_user_data["permissions"] = {}
        if serverid not in target_user_data["permissions"]:
            target_user_data["permissions"][serverid] = {}
        if isinstance(permissions, str):
            import json
            permissions = json.loads(permissions)
        target_user_data["permissions"][serverid][roomid] = permissions

        es.index(index="users", id=userid, body=target_user_data)

        return {"status": "Room permissions added to user"}
    except Exception as e:
        raise Exception(f"Failed to add room permissions to user (userId : {userid}): {str(e)}")

def getRolesFromServer(serverid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        server_data = es.get(index="servers", id=serverid)["_source"]
        if uid in server_data.get("members", []) or user_data["permissions"].get("superuser", False):
            role_ids = server_data["roles"]
        else:
            raise Exception("You are not a member of this server.")
        
        dummy_role = {
			"roleId": "not_a_real_roleId",
			"roleName": "not_a_real_roleName",
			"serverId": "not_a_real_serverId",
			"creation_date": "not_a_real_creation_date",
			"ownerId": "not_a_real_ownerId",
			"roleColor": "#FF0000"
		}

        roles = []
        for role_id in role_ids:
            try:
                role_data = es.get(index="roles", id=role_id)["_source"]
                if type(role_data["permissions"]) == str:
                    role_data["permissions"] = translatePermissions(role_data["permissions"])
                roles.append(role_data)
            except Exception as e:
                dummy_role_copy = dummy_role.copy()
                dummy_role_copy["roleId"] = role_id
                dummy_role_copy["roleName"] = f"Role with ID {role_id} does not exist"
                dummy_role_copy["serverId"] = serverid
                roles.append(dummy_role_copy)

        return roles
    except Exception as e:
        raise Exception(f"Failed to get roles from server: {str(e)}")

def getRole(serverid: str, roleid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        server_data = es.get(index="servers", id=serverid)["_source"]
        if uid in server_data.get("members", []) or user_data["permissions"].get("superuser", False):
            role = es.get(index="roles", id=roleid)["_source"]
        else:
            raise Exception("You are not a member of this server.")
        
        return role
    except Exception as e:
        raise Exception(f"Failed to get role: {str(e)}")

def editRole(serverid: str, roleid: str, role_name: str, permissions, role_color: str, uid: str):
    try:
        if type(permissions) == str:
            permissions = translatePermissions(permissions)

        user_data = es.get(index="users", id=uid)["_source"]
        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}).includes("manage") and server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to edit roles.")

        role_data = es.get(index="roles", id=roleid)["_source"]

        if role_name:
            role_data["roleName"] = role_name
        if permissions:
            role_data["permissions"] = permissions
        if role_color:
            role_data["roleColor"] = role_color

        es.index(index="roles", id=roleid, body=role_data)

        return {"status": "Role edited"}
    except Exception as e:
        raise Exception(f"Failed to edit role: {str(e)}")

def deleteRole(serverid: str, roleid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]
        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}).includes("manage") and server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to delete roles.")

        role_data = es.get(index="roles", id=roleid)["_source"]

        role_data["marked_for_deletion"] = True
        role_data["deletion_timestamp"] = datetime.now().isoformat()

        es.index(index="roles", id=roleid, body=role_data)

        return {"status": f"Role marked for deletion. Confirm within the next {str(deletion_window)}."}
    except Exception as e:
        raise Exception(f"Failed to mark role for deletion: {str(e)}")

def confirmDeleteRole(serverid: str, roleid: str, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]
        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}).includes("manage") and server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to confirm role deletions.")

        role_data = es.get(index="roles", id=roleid)["_source"]

        if not role_data.get("marked_for_deletion", False):
            raise Exception("Role is not marked for deletion.")

        deletion_timestamp = datetime.fromisoformat(role_data["deletion_timestamp"])
        if datetime.now() > deletion_timestamp + deletion_window:
            raise Exception("Confirmation window has expired. Role deletion canceled.")

        es.delete(index="roles", id=roleid)

        return {"status": "Role successfully deleted."}
    except Exception as e:
        raise Exception(f"Failed to confirm role deletion: {str(e)}")

def listServers(uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False):
            query = {
                "size": 1000,
                "query": {
                    "match_all": {}
                }
            }
        else:

            query = {
                "size": 1000,
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"members": uid}},
                            {"match": {"isPublic": True}}
                        ]
                    }
                }
            }
        
        search_result = es.search(index="servers", body=query)
        servers = []

        for hit in search_result["hits"]["hits"]:
            servers.append(hit["_source"])

        return servers
    except Exception as e:
        raise Exception(f"Failed to list servers: {str(e)}")

def downloadServerPfp(server_id: str):
    try:
        server_data = es.get(index="servers", id=server_id)["_source"]

        if "serverImage" not in server_data:
            raise KeyError(f"Server ID {server_id} does not have a 'serverImage' field.")

        file_path = os.path.join("uploads", os.path.basename(server_data["serverImage"]))

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Profile picture for server ID {server_id} does not exist at path: {file_path}")

        file_extension = os.path.splitext(file_path)[1]
        media_type = f"image/{file_extension.lstrip('.')}"
        
        return FileResponse(file_path, media_type=media_type, filename=f"{server_id}{file_extension}")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {str(e)}")
    except KeyError as e:
        raise KeyError(f"Missing key in server data: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")

def changeRoomOrderInServer(serverid: str, room_order: list, uid: str):
    try:
        user_data = es.get(index="users", id=uid)["_source"]
        server_data = es.get(index="servers", id=serverid)["_source"]

        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        if user_data["permissions"].get("superuser", False) == False and "manage" not in user_data["permissions"].get(serverid, {}).includes("manage") and server_data["default_permissions"].get("manage", False):
            raise Exception("You are not allowed to change room order.")

        for room_id in room_order:
            if room_id not in server_data["rooms"]:
                raise Exception(f"Room ID {room_id} is not part of the server's rooms.")
        server_data["rooms"] = room_order

        es.index(index="servers", id=serverid, body=server_data)

        return {"status": "Room order changed"}
    except Exception as e:
        raise Exception(f"Failed to change room order: {str(e)}")

def get_captcha_choices():
    with open(CAPTCHA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    good = list(zip(data["good"]["usernames"], data["good"]["messages"]))
    bad = list(zip(data["bad"]["usernames"], data["bad"]["messages"]))
    good_choices = random.sample(good, 4)
    bad_choice = random.choice(bad)
    choices = good_choices + [bad_choice]
    random.shuffle(choices)
    return [{"username": u, "message": m} for u, m in choices]

def check_captcha_answer(username, message):
    with open(CAPTCHA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return (username, message) in zip(data["bad"]["usernames"], data["bad"]["messages"])

def send_invite_email(target_email: str, message: str, invite_url: str):
    raise NotImplementedError("Email sending is not implemented in this version.")
    smtp_server = "smtp.example.com"
    smtp_port = 587
    smtp_user = "your@email.com"
    smtp_pass = "yourpassword"
    from_addr = smtp_user
    to_addr = target_email

    msg = MIMEText(f"{message}\n\nJoin here: {invite_url}")
    msg["Subject"] = "Server Invitation"
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    except Exception as e:
        raise Exception(f"Failed to send email: {str(e)}")

def create_invite(server_id: str, created_by: str, duration_minutes: int = 1440, one_time: bool = True):
    invite_id = str(uuid.uuid4())
    now = datetime.now()
    invite_doc = {
        "inviteId": invite_id,
        "serverId": server_id,
        "createdBy": created_by,
        "createdAt": now.isoformat(),
        "expiresAt": (now + timedelta(minutes=duration_minutes)).isoformat(),
        "used": False,
        "usedBy": None,
        "oneTime": one_time
    }
    es.index(index="invites", id=invite_id, body=invite_doc)
    return invite_id

def validate_invite(invite_id: str):
    try:
        invite = es.get(index="invites", id=invite_id)["_source"]
        now = datetime.now()
        if invite["used"] and invite["oneTime"]:
            raise Exception("Invite already used.")
        if now > datetime.fromisoformat(invite["expiresAt"]):
            raise Exception("Invite expired.")
        return invite
    except Exception as e:
        raise Exception(f"Invalid invite: {str(e)}")

def use_invite(invite_id: str, user_id: str):
    try:
        invite = es.get(index="invites", id=invite_id)["_source"]
        if (invite["oneTime"] and not invite["used"]) or not invite["oneTime"]:
            invite["used"] = True
            invite["usedBy"] = user_id
            es.index(index="invites", id=invite_id, body=invite)
            return {"status": "Invite used successfully."}
        else:
            raise Exception("Invite already used or invalid.")
    except Exception as e:
        raise Exception(f"Failed to use invite: {str(e)}")

def delete_attachment_from_message(message_id: str, filename: str, user_id: str):
    try:
        message = es.get(index="messages", id=message_id)["_source"]

        user_data = es.get(index="users", id=user_id)["_source"]
        if type(user_data["permissions"]) == str:
            user_data["permissions"] = translatePermissions(user_data["permissions"])
        is_superuser = user_data["permissions"].get("superuser", False)
        if message["userId"] != user_id and not is_superuser:
            raise Exception("You do not have permission to delete this attachment.")

        attachments = message.get("attachments", [])
        new_attachments = [a for a in attachments if a.get("filepath", "").split("/")[-1] != filename]
        if len(attachments) == len(new_attachments):
            raise Exception("Attachment not found.")

        for a in attachments:
            if a.get("filepath", "").split("/")[-1] == filename:
                try:
                    if os.path.exists(a["filepath"]):
                        os.remove(a["filepath"])
                except Exception as e:
                    print(f"Failed to delete file: {e}")

        message["attachments"] = new_attachments
        es.index(index="messages", id=message_id, body=message)
        return {"status": "Attachment deleted"}
    except Exception as e:
        raise Exception(f"Failed to delete attachment: {str(e)}")

def react_to_message(message_id: str, emoji: str, user_id: str):
    try:
        message = es.get(index="messages", id=message_id)["_source"]
        reactions = message.get("reactionList", [])
        found = False
        for reaction in reactions:
            if reaction["emoji"] == emoji:
                found = True
                if user_id in reaction["users"]:
                    reaction["users"].remove(user_id)
                    if not reaction["users"]:
                        reactions.remove(reaction)
                else:
                    reaction["users"].append(user_id)
                break
        if not found:
            reactions.append({"emoji": emoji, "users": [user_id]})
        message["reactionList"] = reactions
        es.index(index="messages", id=message_id, body=message)
        return {"status": "Reaction updated", "reactions": reactions}
    except Exception as e:
        raise Exception(f"Failed to react to message: {str(e)}")

def getRoomById(serverid: str, roomid: str, uid: str):
    try:
        # user_data = es.get(index="users", id=uid)["_source"]

        # server_data = es.get(index="servers", id=serverid)["_source"]

        # if uid not in server_data.get("members", []) and not user_data["permissions"].get("superuser", False):
        #     raise Exception("You are not a member of this server.")

        room_data = es.get(index="rooms", id=roomid)["_source"]

        return room_data
    except Exception as e:
        raise Exception(f"Failed to get room by ID: {str(e)}")

def listUsersInServer(server_id: str, uid: str):
    try:
        # user_data = es.get(index="users", id=uid)["_source"]

        server_data = es.get(index="servers", id=server_id)["_source"]

            
        # if uid not in server_data.get("members", []) and not user_data["permissions"].get("superuser", False):
        #     raise Exception("You are not a member of this server.")
        
        returnList = []
        
        if not server_data.get("isPublic", False):
            for user_id in server_data.get("members", []):
                user = es.get(index="users", id=user_id)["_source"]
                user["_source"].pop("password", None)
                user["_source"].pop("email", None)
                user["_source"].pop("permissions", None)
                user["_source"].pop("creation_date", None)
                user["_source"].pop("marked_for_deletion", None)
                user["_source"].pop("deletion_timestamp", None)
                user["_source"].pop("description", None)
                user["_source"].pop("profile_picture", None)
                returnList.append(user["_source"])
        else:
            query = {
                "size": 1000,
                "query": {
                    "match_all": {}
                }
            }
            users = es.search(index="users", body=query)
            for user in users["hits"]["hits"]:
                user["_source"].pop("password", None)
                user["_source"].pop("email", None)
                user["_source"].pop("permissions", None)
                user["_source"].pop("creation_date", None)
                user["_source"].pop("marked_for_deletion", None)
                user["_source"].pop("deletion_timestamp", None)
                user["_source"].pop("description", None)
                user["_source"].pop("profile_picture", None)
                returnList.append(user["_source"])


        return returnList
    except Exception as e:
        raise Exception(f"Failed to list users in server: {str(e)}")

def search_messages_by_text(location: str, query: str, uid: str):
    es_query = {
        "size": 50,
        "query": {
            "bool": {
                "must": [
                    {"term": {"location.keyword": location}},
                    {"match_phrase_prefix": {"text": query}},
                    {"term": {"deleted": False}}
                ]
            }
        },
        "sort": [{"creation_date": {"order": "desc"}}]
    }
    res = es.search(index="messages", body=es_query)
    return [hit["_source"] for hit in res["hits"]["hits"]]

def search_messages_by_username(location: str, username: str, uid: str):
    user_query = {
        "size": 1,
        "query": {"match": {"username": username}}
    }
    user_res = es.search(index="users", body=user_query)
    if not user_res["hits"]["hits"]:
        return []
    user_id = user_res["hits"]["hits"][0]["_source"]["userId"]
    es_query = {
        "size": 50,
        "query": {
            "bool": {
                "must": [
                    {"term": {"location.keyword": location}},
                    {"term": {"userId": user_id}},
                    {"term": {"deleted": False}}
                ]
            }
        },
        "sort": [{"creation_date": {"order": "desc"}}]
    }
    res = es.search(index="messages", body=es_query)
    return [hit["_source"] for hit in res["hits"]["hits"]]

def kickUserFromServer(server_id: str, user_id: str, admin_id: str):
    admin = es.get(index="users", id=admin_id)["_source"]
    server = es.get(index="servers", id=server_id)["_source"]
    if not (admin["permissions"].get("superuser", False) or server["ownerId"] == admin_id):
        raise Exception("Not allowed")
    if user_id in server.get("members", []):
        server["members"].remove(user_id)
        es.index(index="servers", id=server_id, body=server)
    return {"status": "User kicked from server"}

def getAllUsers():
    query = {
        "size": 1000,
        "query": { "match_all": {} }
    }
    res = es.search(index="users", body=query)
    return [strip_sensitive_user_fields(hit["_source"]) for hit in res["hits"]["hits"]]

