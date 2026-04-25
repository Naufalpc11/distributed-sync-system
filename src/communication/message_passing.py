import asyncio

class MessagePassing:
    def __init__(self):
        self.handlers = {}

    def register_handler(self, msg_type, handler):
        self.handlers[msg_type] = handler

    async def send(self, target, message):
        print(f"Sending message to {target}: {message}")

    async def receive(self, message):
        msg_type = message.get("type")
        if msg_type in self.handlers:
            await self.handlers[msg_type](message)