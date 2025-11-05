import logging
import os
import json
import re
import asyncio
from pathlib import Path
from livekit.api import ChatMessage
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    RoomOutputOptions,
    WorkerOptions,
    AgentStateChangedEvent,
    ConversationItemAddedEvent,
    ChatContext,
    cli,
)
from livekit.plugins import openai, silero, simli
from plugins.whisper_stt import WhisperEndpointSTT
from plugins.kokoro_tts import KokoroTTS
from plugins.piper_tts import PiperTTS

from tools import get_weather, search_and_respond

from prompts import SYSTEM_PROMPT_PERSIAN, SYSTEM_PROMPT_ENGLISH

logger = logging.getLogger("Agent")

project_root = Path(__file__).resolve().parents[2]
env_file = project_root / ".env"
load_dotenv(env_file)

# Tool registry - maps function names to actual functions
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "search_and_respond": search_and_respond,
}

# Speech-to-Text (Whisper) Configuration
WHISPER_BASE_URL = os.getenv("WHISPER_BASE_URL")

# Large Language Model (LLM) Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

# Text-to-Speech (TTS) Configuration
KOKORO_BASE_URL = os.getenv("KOKORO_BASE_URL")
KOKORO_DEFAULT_VOICE = os.getenv("KOKORO_DEFAULT_VOICE")
KOKORO_DEFAULT_SPEED = os.getenv("KOKORO_DEFAULT_SPEED")

PIPER_BASE_URL = os.getenv("PIPER_BASE_URL")

# Simli Avatar Configuration
SIMLI_API_KEY = os.getenv("SIMLI_API_KEY")
SIMLI_FACE_ID = os.getenv("SIMLI_FACE_ID")

# VAD Configuration
VAD_MIN_SPEECH_DURATION = os.getenv("VAD_MIN_SPEECH_DURATION", "0.1")
VAD_MIN_SILENCE_DURATION = os.getenv("VAD_MIN_SILENCE_DURATION", "0.5")
VAD_PREFIX_PADDING = os.getenv("VAD_PREFIX_PADDING", "0.2")
VAD_MAX_BUFFERED_SPEECH = os.getenv("VAD_MAX_BUFFERED_SPEECH", "30.0")

TOOL_CALL_PATTERN = re.compile(r'\$tool_calls\s*\n(\[.*?\])\s*\n\$', re.DOTALL)


async def parse_and_execute_tool_calls(content: str):
    """
    Detects tool calls in format: $tool_calls [...] $
    """
    if len(content) == 0:
        return None
   
    results = []
    try:
        # Extract JSON array from the pattern: $tool_calls\n[...]\n$
        match = TOOL_CALL_PATTERN.search(content)
        if match:
            tool_calls_json = match.group(1)
            tool_calls = json.loads(tool_calls_json)
            
            if tool_calls:
                for tool_call in tool_calls:
                    function_name = tool_call.get("function")
                    args = tool_call.get("args", {})
                    
                    # Validate tool call structure
                    if not function_name or not isinstance(function_name, str):
                        logger.warning(f"Invalid tool call - missing or invalid function name: {tool_call}")
                        continue
                    
                    if function_name not in TOOL_REGISTRY:
                        logger.error(f"Unknown function: {function_name}")
                        continue
                    
                    func = TOOL_REGISTRY[function_name]
                    
                    # Handle async functions
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**args)
                    else:
                        result = func(**args)
                    
                    results.append(f"{function_name} returned: {result}")
                
                return "\n".join(results) if results else None
                
    except json.JSONDecodeError as e:
        logger.error(f"[TOOL] JSON parsing error: {e}")
    except Exception as e:
        logger.error(f"[TOOL] Error executing tool: {e}", exc_info=True)
    
    return None


class Assistant(Agent):
    def __init__(self, instructions: str, tools: list = None) -> None:
        super().__init__(
                instructions=instructions,
                tools=tools
        )

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
        if len(turn_ctx.items) >= 2 and turn_ctx.items[-1].role == "user":
            new_message.content = [f"{turn_ctx.items[-1].text_content} {' '}{new_message.text_content}"]
            # pop the incomplete message
            turn_ctx.items.pop(-1)
            await self.update_chat_ctx(turn_ctx)
            logger.warning("Consecutive user messages merged")


def prewarm(proc: JobProcess):
    proc.userdata["llm"] = openai.LLM(
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key="dummy",
            tool_choice="auto",
        )
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=float(VAD_MIN_SPEECH_DURATION),
        min_silence_duration=float(VAD_MIN_SILENCE_DURATION),
        prefix_padding_duration=float(VAD_PREFIX_PADDING),
        max_buffered_speech=float(VAD_MAX_BUFFERED_SPEECH),
    )
    
    proc.userdata["tts_factory"] = {
        "en": lambda: KokoroTTS(
                base_url=KOKORO_BASE_URL,
                voice=KOKORO_DEFAULT_VOICE,
                speed=KOKORO_DEFAULT_SPEED,
                buffer_sentences=True,
                flush_timeout=1.5,
                inter_chunk_pause=1,
            ),
        "fa": lambda: PiperTTS(
                base_url=PIPER_BASE_URL,
                sample_rate=22050,
            )
    }
    proc.userdata["stt_factory"] = lambda lang: WhisperEndpointSTT(
            api_url=WHISPER_BASE_URL,
            language=lang,
        )

    logger.info("[OK] LLM and VAD prewarmed. STT/TTS will be initialized based on participant language.")


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Connect to the room first
    await ctx.connect()
    
    # Wait for participant to connect to get their language preference
    participant = await ctx.wait_for_participant()
    
    # Extract language from participant metadata
    try:
        if participant.metadata:
            metadata = json.loads(participant.metadata)
            language = metadata.get("language", os.getenv("LANGUAGE", "en"))
    except Exception as e:
        logger.warning(f"Failed to parse participant metadata, using default language: {e}")
    
    # Initialize STT and TTS based on participant's language
    stt = ctx.proc.userdata["stt_factory"](language)
    tts = ctx.proc.userdata["tts_factory"].get(language, ctx.proc.userdata["tts_factory"]["en"])()
    
    logger.info(f"\033[0;34mInitialized agent with language: {language}\033[0m")

    session = AgentSession(
        stt=stt,
        llm=ctx.proc.userdata["llm"],
        tts=tts,
        turn_detection="vad",
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,
    )

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"Participant connected: {participant.identity}")
        
    @ctx.room.on("participant_disconnected") 
    def on_participant_disconnected(participant):
        logger.info(f"Participant disconnected: {participant.identity}")

    @ctx.room.on("data_received")
    def on_data_received(data_packet):
        """Handle data messages from frontend (e.g., text input from MessageInput component)"""
        try:
            # Decode the data packet
            data_str = data_packet.data.decode('utf-8')
            logger.info(f"Received data message: {data_str}")
            
            # Check if this is from the lk.chat topic (MessageInput component)
            if data_packet.topic == "lk.chat":
                # Parse the JSON message from MessageInput
                message_data = json.loads(data_str)
                user_message = message_data.get("message", "").strip()
                
                if user_message:
                    logger.info(f"\033[38;5;46m[TEXT INPUT] User: {user_message}\033[0m")
                    # Generate reply using the session
                    session.generate_reply(user_input=user_message)
                else:
                    logger.warning("Received empty message from lk.chat topic")
            else:
                # Handle other data topics (like voice config)
                try:
                    config_data = json.loads(data_str)
                    if config_data.get("type") == "voice_config":
                        voice = config_data.get("voice")
                        logger.info(f"Voice configuration received: {voice}")
                        # Voice config is handled elsewhere, just log it
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON data on topic {data_packet.topic}: {data_str}")
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse data message as JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling data message: {e}", exc_info=True)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event: AgentStateChangedEvent):
        logger.info(f"Agent state changed: {event.old_state} -> {event.new_state}")

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event: ConversationItemAddedEvent):
        logger.info(f"\033[38;5;208m{event.item.role} : {event.item.text_content}\033[0m")
        # Detect and execute tool calls
        if event.item.role == "assistant" and "$tool_calls" in event.item.text_content:
            async def handle_tool_call():
                result = await parse_and_execute_tool_calls(event.item.text_content)
                if result:
                    session.generate_reply(user_input=result)
            asyncio.create_task(handle_tool_call())

    # Select system prompt based on language
    system_prompt = SYSTEM_PROMPT_PERSIAN if language == "fa" else SYSTEM_PROMPT_ENGLISH
    assistant = Assistant(instructions=system_prompt, tools=[search_and_respond])
  
    simli_avatar = simli.AvatarSession(
                simli_config=simli.SimliConfig(
                    api_key=SIMLI_API_KEY,
                    face_id=SIMLI_FACE_ID,
                    max_session_length=600,
                    max_idle_time=600, 
                ),
            )
    
    # ctx.connect() already called above - no need to call again
    
    await asyncio.gather(
        simli_avatar.start(session, room=ctx.room),
        session.start(
            agent=assistant,
            room=ctx.room,
            room_input_options=RoomInputOptions(),
            room_output_options=RoomOutputOptions(),
        )
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
