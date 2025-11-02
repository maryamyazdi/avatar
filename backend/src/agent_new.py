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
    ChatContext,
    FunctionTool,
    ModelSettings,
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

LANGUAGE = os.getenv("LANGUAGE")

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

    async def llm_node(
        self, chat_ctx: ChatContext, tools: list[FunctionTool], model_settings: ModelSettings
    ):
        """
        Override llm_node to intercept messages before they reach the LLM.
        This allows us to detect and merge two consecutive user messages.
        """
        if len(chat_ctx.items) >= 2:
            last_message = chat_ctx.items[-1]
            second_last_message = chat_ctx.items[-2]
            
            if last_message.role == "user" and second_last_message.role == "user":
                last_content = last_message.content[0]
                second_last_content = second_last_message.content[0]

                merged_content = f"{second_last_content}{' '}{last_content}"
                last_message.content[0] = merged_content
                chat_ctx.items.pop(-2)
                logger.warning("Merged consecutive user messages.")
                
        # Call the default LLM node to proceed with normal processing
        async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
            yield chunk


def prewarm(proc: JobProcess):
    proc.userdata["stt"] = WhisperEndpointSTT(
            api_url=WHISPER_BASE_URL,
            language=LANGUAGE,
        )
    proc.userdata["llm"] = openai.LLM(
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key="dummy",
            tool_choice="auto",
        )
    if LANGUAGE == "en":
        proc.userdata["tts"] = KokoroTTS(
                base_url=KOKORO_BASE_URL,
                voice=KOKORO_DEFAULT_VOICE,
                speed=KOKORO_DEFAULT_SPEED,
                buffer_sentences=True,
                flush_timeout=1.5,
                inter_chunk_pause=1,
            )
    elif LANGUAGE == "fa":
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
        logger.info(f"\033[38;5;208m{event.item.role} : {event.item.content[0]}\033[0m")   
        items_to_show = session.history.items[-6:] if len(session.history.items) > 6 else session.history.items
        logger.info(f"\033[35mRoles so far: {[item.role for item in items_to_show]}\033[0m")
        
        # Detect and execute tool calls
        if event.item.role == "assistant":
            response = event.item.content[0] if isinstance(event.item.content[0], str) else str(event.item.content[0])
            if "$tool_calls" in response:
                async def handle_tool_call():
                    result = await parse_and_execute_tool_calls(response)
                    if result:
                        session.generate_reply(user_input=result)
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
