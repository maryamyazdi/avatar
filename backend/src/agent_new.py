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

    # async def llm_node(
    #     self, chat_ctx: ChatContext, tools: list[FunctionTool], model_settings: ModelSettings
    # ):
    #     """
    #     Override llm_node to intercept messages before they reach the LLM.
    #     This allows us to detect and merge two consecutive user messages.
    #     """
    #     if len(chat_ctx.items) >= 2:
    #         last_message = chat_ctx.items[-1]
    #         second_last_message = chat_ctx.items[-2]
            
    #         if last_message.role == "user" and second_last_message.role == "user":
    #             last_content = last_message.content[0]
    #             second_last_content = second_last_message.content[0]

    #             merged_content = f"{second_last_content}{' '}{last_content}"

    #             logger.warning(f"chat_ctx before deleting:{[item.role for item in chat_ctx.items]}")
            
    #             chat_ctx.items.pop(-2)
    #             chat_ctx.items[-1].content[0] = merged_content
    #             logger.info(f"\033[36m [LLM node] Last message:{chat_ctx.items[-1].content[0]}\033[0m")

    #             logger.warning(f"chat_ctx after deleting:{[item.role for item in chat_ctx.items]}")
                
    #     # Call the default LLM node to proceed with normal processing
    #     async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
    #         yield chunk


    # async def transcription_node(self, session: AgentSession, user_msg: str):
    #     """
    #     Override transcription_node to check for consecutive user messages
    #     and merge them BEFORE adding to history.
    #     """
    #     # Check if the last message in history is from the user
    #     if len(session.history.items) > 0 and session.history.items[-1].role == "user":
    #         if session.history.items[-2].role == "user":
    #             session.history.items.pop(-1)
    #             session.history.items[-1].content[0] = f"{session.history.items[-1].content[0]} {user_msg}"
    #             logger.warning(f"\033[0;33mMerged consecutive user input: '{session.history.items[-1].content[0]}' + '{user_msg}' = '{session.history.items[-1].content[0]}'\033[0m")
    #             logger.info(f"\033[36m [transcription_node] Last message:{session.history.items[-1].content[0]}\033[0m")
    #             return session.history.items[-1].content[0]
    #         else:
    #             session.history.items.append(ConversationItemAddedEvent(role="user", content=[user_msg]))
    #             return user_msg
        
    #     # If not consecutive, process normally
    #     return await Agent.default.transcription_node(self, session, user_msg)


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
            logger.info(f"Participant language preference: {language}")
    except Exception as e:
        logger.warning(f"Failed to parse participant metadata, using default language: {e}")
    
    # Initialize STT and TTS based on participant's language
    stt = ctx.proc.userdata["stt_factory"](language)
    tts = ctx.proc.userdata["tts_factory"].get(language, ctx.proc.userdata["tts_factory"]["en"])()
    
    logger.info(f"Initialized agent with language: {language}")

    session = AgentSession(
        stt=stt,
        llm=ctx.proc.userdata["llm"],
        tts=tts,
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
        # session.history = assistant.chat_ctx
        logger.info(f"\033[38;5;208m{event.item.role} : {event.item.content[0]}\033[0m")
        items_to_show = session.history.items[-6:] if len(session.history.items) > 6 else session.history.items
        logger.info(f"\033[35mRoles so far: {[item.role for item in items_to_show]}\033[0m")

        if event.item.role == "user" and len(session.history.items) >= 2:
            if session.history.items[-2].role == "user":
                session.history.items.pop(-1)
                items_to_show = session.history.items[-6:] if len(session.history.items) > 6 else session.history.items
                logger.info(f"\033[35mRoles so far after merging: {[item.role for item in items_to_show]}\033[0m")
                logger.info(f"\033[36m [on_conversation_item_added] Last message:{session.history.items[-1].content[0]}\033[0m")
        
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
    
    @session.on("error")
    def _on_error(error):
        """Simple error handler - just reset conversation and continue."""
        logger.error(f"Session error: {error}", exc_info=True)
        
        # For any LLM error, reset conversation to system message
        if error.type == "llm_error":
            logger.warning(f"Problematic history: {[item.role for item in session.history.items]}")
            
            try:
                # Keep only system message
                system_msg = None
                for item in session.history.items:
                    if item.role == "system":
                        system_msg = item
                        break
                
                session.history.items.clear()
                if system_msg:
                    session.history.items.append(system_msg)
                
                logger.info("Conversation reset - ready for new interaction")
                
            except Exception as e:
                logger.error(f"Failed to reset: {e}")

    assistant = Assistant(instructions=SYSTEM_PROMPT, tools=[search_and_respond, get_weather])
  
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
