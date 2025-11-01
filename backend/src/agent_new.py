import logging
import os
import json
import re
import asyncio
from pathlib import Path
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
    BackgroundAudioPlayer,
    AudioConfig,
    BuiltinAudioClip,
    cli,
)
from livekit.plugins import openai, silero, simli
from plugins.whisper_stt import WhisperEndpointSTT
from plugins.kokoro_tts import KokoroTTS
from plugins.piper_tts import PiperTTS

from tools import get_weather, search_and_respond

from prompts import SYSTEM_PROMPT

logger = logging.getLogger("Agent")

# Load environment variables from project root
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
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE")

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



async def parse_and_execute_tool_calls(content: str):
    """
    Detects tool calls in format: $tool_calls [...] $
    """
    if len(content) == 0:
        return None
    
    text = content[0] if isinstance(content[0], str) else str(content[0])
    
    results = []
    try:
        # Extract JSON array from the pattern: $tool_calls\n[...]\n$
        match = re.search(r'\$tool_calls\s*\n(\[.*?\])\s*\n\$', text, re.DOTALL)
        if not match:
            logger.error("Failed to extract tool call JSON")
            return None
        
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


def prewarm(proc: JobProcess):
    proc.userdata["stt"] = WhisperEndpointSTT(
            api_url=WHISPER_BASE_URL,
            language=WHISPER_LANGUAGE
        )
    proc.userdata["llm"] = openai.LLM(
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key="dummy",
            tool_choice="auto",
        )
    # Kokoro TTS (Old - Commented Out)
    # proc.userdata["tts"] = KokoroTTS(
    #         base_url=KOKORO_BASE_URL,
    #         voice=KOKORO_DEFAULT_VOICE,
    #         speed=KOKORO_DEFAULT_SPEED,
    #         buffer_sentences=True,
    #         flush_timeout=1.5,
    #         inter_chunk_pause=1,
    #     )
    
    proc.userdata["tts"] = PiperTTS(
            base_url=PIPER_BASE_URL,
            sample_rate=22050,
        )
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=float(VAD_MIN_SPEECH_DURATION),
        min_silence_duration=float(VAD_MIN_SILENCE_DURATION),
        prefix_padding_duration=float(VAD_PREFIX_PADDING),
        max_buffered_speech=float(VAD_MAX_BUFFERED_SPEECH),
    )

    logger.info("[OK] STT, LLM, TTS, and VAD loaded.")


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=ctx.proc.userdata["stt"],
        llm=ctx.proc.userdata["llm"],
        tts=ctx.proc.userdata["tts"],
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,
    )
    
    background_audio = BackgroundAudioPlayer(
        thinking_sound=AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8)
    )
    
    tool_executing = {"active": False, "audio_handle": None}

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"Participant connected: {participant.identity}")
        
    @ctx.room.on("participant_disconnected") 
    def on_participant_disconnected(participant):
        logger.info(f"Participant disconnected: {participant.identity}")

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event: AgentStateChangedEvent):
        logger.info(f"Agent state changed: {event.old_state} -> {event.new_state}")

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event: ConversationItemAddedEvent):
        logger.info(f"\033[38;5;208m{event.item.role} : {event.item.content}\033[0m")   
        logger.info(f"\033[35mRoles so far: {[item.role for item in session.history.items]}\033[0m")
        
        # Detect and execute tool calls
        if event.item.role == "assistant":
            async def handle_tool_call():
                if "$tool_calls" in event.item.content:
                    result = await parse_and_execute_tool_calls(event.item.content)
                    if result:
                        tool_executing["active"] = True
                        tool_executing["audio_handle"] = background_audio.play(BuiltinAudioClip.KEYBOARD_TYPING2, loop=True)
                        
                        session.generate_reply(user_input=result)
                        
                        tool_executing["active"] = False
                        if tool_executing["audio_handle"]:
                            tool_executing["audio_handle"].stop()
                            tool_executing["audio_handle"] = None
                        return result
            asyncio.create_task(handle_tool_call())    

    assistant = Assistant(instructions=SYSTEM_PROMPT, tools=[search_and_respond, get_weather])
  
    simli_avatar = simli.AvatarSession(
                simli_config=simli.SimliConfig(
                    api_key=SIMLI_API_KEY,
                    face_id=SIMLI_FACE_ID,
                ),
            )
    
    await ctx.connect()
    
    await background_audio.start(room=ctx.room, agent_session=session)
    
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
