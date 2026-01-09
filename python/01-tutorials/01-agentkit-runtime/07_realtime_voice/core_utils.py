import asyncio
import json
import logging
import os
import websockets
import traceback
from websockets.exceptions import ConnectionClosed
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
stream_logger = logging.getLogger(__name__)


# Constants
load_dotenv()

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
MODEL = os.environ.get("MODEL")
VOICE_NAME = os.environ.get("VOICE_NAME")
GOOGLE_GENAI_USE_VERTEXAI = "FALSE"


# Audio sample rates for input/output
RECEIVE_SAMPLE_RATE = 24000  # Rate of audio received from Gemini
SEND_SAMPLE_RATE = 16000  # Rate of audio sent to Gemini

# System instruction used by both implementations
SYSTEM_INSTRUCTION = """
You are NaviGo AI, a friendly and helpful travel assistant.
You talk to user like an Women Indian Travel Agent in late 40s who is very knowledgeable about travel destinations, routes, and local attractions.
Your goal is to provide accurate and relevant travel information to users.
You should introduce yourself at the beginning of the conversation: Be innovative and creative but mention your name Navigo AI and what you do.
You can use the google_search tool to answer generic travel queries.
When a user has any question regarding location , navigation it uses google maps mcp tools.
Avoid Giving Any Information about yourself, your capabilities, or the tools you use.

Be clear in your responses. Always keep your responses concise and to the point.
If you don't know the answer to a question, politely inform the user that you don't have that information.
If the user asks for information that is not related to travel, politely inform them that you cannot assist with that.
"""

# Base WebSocket server class that handles common functionality


class BaseStreamServer:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.active_connections = {}  # Store client connections

    async def start_server(self):
        stream_logger.info(f"Starting stream server on {self.host}:{self.port}")
        async with websockets.serve(self.manage_connection, self.host, self.port):
            await asyncio.Future()  # Run forever

    async def manage_connection(self, websocket):
        """Handle a new client connection"""
        connection_id = id(websocket)
        stream_logger.info(f"New connection established: {connection_id}")

        # Send ready message to client
        await websocket.send(json.dumps({"type": "ready"}))

        try:
            # Start processing the stream for this client
            await self.handle_stream(websocket, connection_id)
        except ConnectionClosed:
            stream_logger.info(f"Connection closed: {connection_id}")
        except Exception as e:
            stream_logger.error(f"Error handling connection {connection_id}: {e}")
            stream_logger.error(traceback.format_exc())
        finally:
            # Clean up
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]

    async def handle_stream(self, websocket, client_id):
        """
        Process data stream from the client. This is an abstract method that
        subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement handle_stream")
