import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Message


def clean_room_name(room_name):
    room_name = room_name or "general"
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", room_name)[:80]


def direct_room_user_ids(room_name):
    match = re.fullmatch(r"dm_(\d+)_(\d+)", room_name or "")
    if not match:
        return None
    return {int(match.group(1)), int(match.group(2))}


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_name = clean_room_name(self.scope["url_route"]["kwargs"].get("room_name"))
        self.room_group_name = f"chat_{self.room_name}"
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated or not self.can_access_room():
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        text = (content.get("text") or "").strip()
        if not text:
            await self.send_json({"type": "error", "detail": "Message text is required."})
            return

        receiver_id = self.get_receiver_id(content.get("receiver"))
        message = await self.create_message(text, receiver_id)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "message": message,
            },
        )

    async def chat_message(self, event):
        await self.send_json(event["message"])

    def can_access_room(self):
        user_ids = direct_room_user_ids(self.room_name)
        return user_ids is None or self.user.id in user_ids

    def get_receiver_id(self, requested_receiver_id):
        user_ids = direct_room_user_ids(self.room_name)
        if not user_ids:
            return requested_receiver_id or None
        other_ids = user_ids - {self.user.id}
        return other_ids.pop() if other_ids else None

    @database_sync_to_async
    def create_message(self, text, receiver_id=None):
        receiver_id = receiver_id or None
        message = Message.objects.create(
            sender=self.user,
            receiver_id=receiver_id,
            room=self.room_name,
            text=text,
        )
        return {
            "id": message.id,
            "sender": message.sender_id,
            "sender_name": message.sender.full_name,
            "sender_avatar": message.sender.get_avatar_url(),
            "receiver": message.receiver_id,
            "room": message.room,
            "text": message.text,
            "timestamp": message.timestamp.isoformat(),
            "is_read": message.is_read,
        }
