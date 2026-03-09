from core_utils import (
    BaseStreamServer,
    stream_logger,
    MODEL,
    VOICE_NAME,
    SEND_SAMPLE_RATE,
    SYSTEM_INSTRUCTION,
)
import asyncio
import json
import base64
import traceback

# Import Google ADK components
from google.adk.agents import LiveRequestQueue

from veadk import Agent, Runner
from veadk.realtime import DoubaoRealtimeVoice
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


# Import common components

# Function tool for order status


class StreamingService(BaseStreamServer):
    """Real-time streaming service for audio and video data."""

    def __init__(self, host="0.0.0.0", port=8000):
        super().__init__(host, port)

        # Initialize ADK components
        self.agent = Agent(
            name="voice_assistant_agent",
            model=MODEL,
            instruction=SYSTEM_INSTRUCTION,
        )

        # Create session service
        self.session_service = InMemorySessionService()

    async def handle_stream(self, websocket, client_id):
        """Process real-time data streams from the client."""
        # Store client reference
        self.active_connections[client_id] = websocket

        # Create a new session for the client
        user_id = f"user_{client_id}"
        session_id = f"session_{client_id}"
        await self.session_service.create_session(
            app_name="streaming_assistant",
            user_id=user_id,
            session_id=session_id,
        )

        # Create runner
        runner = Runner(
            app_name="streaming_assistant",
            agent=self.agent,
            session_service=self.session_service,
        )
        stream_logger.info(f"RealtimeVoice model: {DoubaoRealtimeVoice.model_config}")

        # Create live request queue
        live_request_queue = LiveRequestQueue()

        # Create run config with audio settings
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE_NAME
                    )
                )
            ),
            response_modalities=["AUDIO"],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )

        # Queues for audio and video data from the client
        audio_queue = asyncio.Queue()
        video_queue = asyncio.Queue()

        # Task to process incoming WebSocket messages
        async def receive_client_messages():
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("type") == "audio":
                        audio_bytes = base64.b64decode(data.get("data", ""))
                        await audio_queue.put(audio_bytes)
                    elif data.get("type") == "video":
                        video_bytes = base64.b64decode(data.get("data", ""))
                        video_mode = data.get("mode", "webcam")
                        await video_queue.put({"data": video_bytes, "mode": video_mode})
                    elif data.get("type") == "end":
                        stream_logger.info(
                            "Client has concluded data transmission for this turn."
                        )
                    elif data.get("type") == "text":
                        stream_logger.info(
                            f"Received text from client: {data.get('data')}"
                        )
                except json.JSONDecodeError:
                    stream_logger.error("Could not decode incoming JSON message.")
                except Exception as e:
                    stream_logger.error(
                        f"Exception while processing client message: {e}"
                    )

        async def send_audio_to_service():
            while True:
                data = await audio_queue.get()
                live_request_queue.send_realtime(
                    types.Blob(
                        data=data, mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}"
                    )
                )
                audio_queue.task_done()

        async def send_video_to_service():
            while True:
                video_data = await video_queue.get()
                video_bytes = video_data.get("data")
                video_mode = video_data.get("mode", "webcam")
                stream_logger.info(
                    f"Transmitting video frame from source: {video_mode}"
                )
                live_request_queue.send_realtime(
                    types.Blob(data=video_bytes, mime_type="image/jpeg")
                )
                video_queue.task_done()

        async def receive_service_responses():
            # Track user and model outputs between turn completion events
            input_texts = []
            output_texts = []
            current_session_id = None

            # Flag to track if we've seen an interruption in the current turn
            interrupted = False
            audio_buffer = b""

            # Process responses from the agent
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                # Check for turn completion or interruption using string matching
                # This is a fallback approach until a proper API exists
                event_str = str(event)

                # If there's a session resumption update, store the session ID
                if (
                    hasattr(event, "session_resumption_update")
                    and event.session_resumption_update
                ):
                    update = event.session_resumption_update
                    if update.resumable and update.new_handle:
                        current_session_id = update.new_handle
                        stream_logger.info(
                            f"Established new session with handle: {current_session_id}"
                        )
                        # Send session ID to client
                        session_id_msg = json.dumps(
                            {"type": "session_id", "data": current_session_id}
                        )
                        await websocket.send(session_id_msg)

                # Handle content
                if (
                    event.content
                    and hasattr(event.content, "parts")
                    and event.content.parts
                ):
                    for part in event.content.parts:
                        # Process audio content
                        if hasattr(part, "inline_data") and part.inline_data:
                            b64_audio = base64.b64encode(part.inline_data.data).decode(
                                "utf-8"
                            )
                            audio_buffer += part.inline_data.data
                            await websocket.send(
                                json.dumps({"type": "audio", "data": b64_audio})
                            )

                        # Process text content
                        if hasattr(part, "text") and part.text:
                            # Check if this is user or model text based on content role
                            if (
                                hasattr(event.content, "role")
                                and event.content.role == "user"
                            ):
                                # User text should be sent to the client
                                if "partial=True" in event_str:
                                    await websocket.send(
                                        json.dumps(
                                            {
                                                "type": "user_transcript",
                                                "data": part.text,
                                            }
                                        )
                                    )
                                input_texts.append(part.text)
                            else:
                                # From the logs, we can see the duplicated text issue happens because
                                # we get streaming chunks with "partial=True" followed by a final consolidated
                                # response with "partial=None" containing the complete text

                                # Check in the event string for the partial flag
                                # Only process messages with "partial=True"
                                if "partial=True" in event_str:
                                    await websocket.send(
                                        json.dumps({"type": "text", "data": part.text})
                                    )
                                    output_texts.append(part.text)
                                # Skip messages with "partial=None" to avoid duplication

                # Check for interruption
                if event.interrupted and not interrupted:
                    stream_logger.warning("User has interrupted the stream.")
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "interrupted",
                                "data": "Response interrupted by user input",
                            }
                        )
                    )
                    interrupted = True

                if event.input_transcription and hasattr(
                    event.input_transcription, "text"
                ):
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "user_transcript",
                                "data": event.input_transcription.text,
                            }
                        )
                    )

                if event.output_transcription and hasattr(
                    event.output_transcription, "text"
                ):
                    await websocket.send(
                        json.dumps(
                            {"type": "text", "data": event.output_transcription.text}
                        )
                    )

                # Check for turn completion
                if event.turn_complete:
                    # Only send turn_complete if there was no interruption
                    if not interrupted:
                        stream_logger.info("The model has completed its turn.")
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "turn_complete",
                                    "session_id": current_session_id,
                                }
                            )
                        )

                    # # Log collected transcriptions for debugging
                    # if input_texts:
                    #     # Get unique texts to prevent duplication
                    #     unique_texts = list(dict.fromkeys(input_texts))
                    #     stream_logger.info(
                    #         f"Transcribed user speech: {' '.join(unique_texts)}")
                    #
                    # if output_texts:
                    #     # Get unique texts to prevent duplication
                    #     unique_texts = list(dict.fromkeys(output_texts))
                    #     stream_logger.info(
                    #         f"Generated model response: {' '.join(unique_texts)}")

                    # Reset for next turn
                    input_texts = []
                    output_texts = []
                    interrupted = False

        tasks = [
            asyncio.create_task(receive_client_messages()),
            asyncio.create_task(send_audio_to_service()),
            asyncio.create_task(send_video_to_service()),
            asyncio.create_task(receive_service_responses()),
        ]
        # Start all tasks
        # 等待所有任务完成（添加异常处理）
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                stream_logger.error(f"任务执行异常: {result}")


async def main():
    """Main function to start the server"""
    server = StreamingService()
    await server.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        stream_logger.info("Server is shutting down.")
    except Exception as e:
        stream_logger.critical(f"A fatal unhandled exception occurred: {e}")
        import traceback

        traceback.print_exc()
