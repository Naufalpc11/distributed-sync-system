import os

class Config:
    NODE_ID = os.getenv("NODE_ID", "node-1")
    HOST = os.getenv("HOST", "localhost")
    PORT = int(os.getenv("PORT", 8000))