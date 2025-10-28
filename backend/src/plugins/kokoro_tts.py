import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional, AsyncIterator, Literal

from livekit.agents import (
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
)
from livekit import rtc
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
from livekit.agents.utils import is_given
import httpx
import openai


logger = logging.getLogger("kokoro-tts")

# Constants
TTS_SAMPLE_RATE = 24000
TTS_CHANNELS = 1

# Type definitions
TTSVoices = Literal["echo", "af_heart", "af_bella", "af_sky"]

class TextBuffer:
    """Buffers text chunks and releases complete sentences/phrases for more natural TTS."""
    
    def __init__(self, flush_timeout: float = 1.2, max_chunk_length: int = 120):
        self._buffer = ""
        self._flush_timeout = flush_timeout
        self._max_chunk_length = max_chunk_length
        self._last_update = 0.0
        
        # English sentence ending patterns
        self._sentence_endings = re.compile(r'[.!?]+(?:\s|$)')
        self._strong_endings = re.compile(r'[.!?]{2,}(?:\s|$)')  # Multiple punctuation
        
        # Long sentence break patterns for English
        self._long_sentence_breaks = re.compile(r'\b(?:because|since|when|while|although|though|if|unless|after|before|as)\s+', re.IGNORECASE)
        
    def add_text(self, text: str) -> list[str]:
        """Add text to buffer and return natural speech chunks ready for TTS."""
        import time
        
        # Preprocess text for better speech synthesis
        processed_text = self._preprocess_for_speech(text)
        self._buffer += processed_text
        self._last_update = time.time()
        
        chunks = []
        
        # Process buffer for natural speech chunks
        while self._buffer.strip():
            chunk = self._extract_next_chunk()
            if chunk:
                # Post-process the chunk for final speech optimization
                chunk = self._optimize_chunk_for_speech(chunk)
                chunks.append(chunk)
            else:
                break
        
        return chunks
    
    def _preprocess_for_speech(self, text: str) -> str:
        """Preprocess text to be more speech-friendly."""
        # Add slight pauses after certain punctuation for more natural flow
        text = re.sub(r'([.!?])\s+', r'\1 ', text)  # Normalize spacing
        
        # Add pauses after commas for more natural speech rhythm
        # Using ellipsis (...) which TTS engines interpret as pauses (~1.5 seconds)
        text = re.sub(r',\s*', '... ', text)  # Replace comma with ellipsis for pause
        text = re.sub(r'([;:])\s*', r'\1 ', text)  # Ensure space after semicolons/colons
        
        # Convert some written forms to spoken forms
        text = re.sub(r'\be\.g\.\s*', 'for example... ', text, flags=re.IGNORECASE)
        text = re.sub(r'\bi\.e\.\s*', 'that is... ', text, flags=re.IGNORECASE)
        text = re.sub(r'\betc\.\s*', 'and so on... ', text, flags=re.IGNORECASE)
        text = re.sub(r'\bvs\.\s*', 'versus ', text, flags=re.IGNORECASE)
        
        # Handle numbers and abbreviations more naturally
        text = re.sub(r'\b(\d+)%', r'\1 percent', text)
        text = re.sub(r'\$(\d+)', r'\1 dollars', text)
        
        return text
    
    def _optimize_chunk_for_speech(self, chunk: str) -> str:
        """Final optimization of a chunk for natural speech."""
        chunk = chunk.strip()
        if not chunk:
            return chunk
            
        # Ensure proper spacing and punctuation
        chunk = re.sub(r'\s+', ' ', chunk)  # Normalize whitespace
        
        # Ensure ellipsis (pause markers) have proper spacing
        chunk = re.sub(r'\.{3,}\s*', '... ', chunk)  # Normalize ellipsis spacing
            
        return chunk
    
    def _extract_next_chunk(self) -> str:
        """Extract the next natural speech chunk from the buffer."""
        buffer = self._buffer.strip()
        if not buffer:
            return ""
        
        # Priority 1: Complete sentences (highest priority)
        sentence_match = self._sentence_endings.search(buffer)
        if sentence_match:
            chunk = buffer[:sentence_match.end()].strip()
            self._buffer = buffer[sentence_match.end():].lstrip()
            
            # If sentence is too long, try to break it at natural points
            if len(chunk) > self._max_chunk_length:
                return self._break_long_sentence(chunk)
            return chunk

        
        # Priority 3: Comma/pause breaks (if buffer is getting long)
        if len(buffer) > self._max_chunk_length // 2:
            # Define pause patterns for natural speech breaks
            pause_patterns = re.compile(r'[,;:]\s+')
            pause_match = pause_patterns.search(buffer)
            if pause_match and pause_match.start() > 15:  # Minimum chunk size
                chunk = buffer[:pause_match.end()].strip()
                self._buffer = buffer[pause_match.end():].lstrip()
                return chunk
        
        # Priority 4: Long sentence subordinate clause breaks
        if len(buffer) > self._max_chunk_length:
            clause_match = self._long_sentence_breaks.search(buffer)
            if clause_match and clause_match.start() > 20:
                chunk = buffer[:clause_match.start()].strip()
                self._buffer = buffer[clause_match.start():].lstrip()
                return chunk
        
        # No natural break found
        return ""
    
    def _break_long_sentence(self, sentence: str) -> str:
        """Break a long sentence at the most natural point."""
        # Try to break at phrase boundaries within the sentence
        words = sentence.split()
        if len(words) <= 8:  # Short enough, don't break
            return sentence
        
        # Look for natural break points in the middle third of the sentence
        start_idx = len(words) // 3
        end_idx = 2 * len(words) // 3
        
        for i in range(start_idx, end_idx):
            word = words[i].lower()
            # Break after conjunctions and transition words
            if word in ['and', 'but', 'or', 'so', 'yet', 'for', 'nor', 'because', 'since', 'although', 'while', 'when', 'where', 'if', 'unless', 'until', 'after', 'before']:
                first_part = ' '.join(words[:i+1])
                remaining = ' '.join(words[i+1:])
                self._buffer = remaining + ' ' + self._buffer
                return first_part
        
        # No good break point found, return as is
        return sentence
    
    def should_flush(self) -> bool:
        """Check if buffer should be flushed due to timeout."""
        import time
        
        if not self._buffer.strip():
            return False
            
        return (time.time() - self._last_update) >= self._flush_timeout
    
    def flush(self) -> Optional[str]:
        """Flush remaining buffer content."""
        if self._buffer.strip():
            content = self._buffer.strip()
            self._buffer = ""
            return content
        return None
    
    def has_content(self) -> bool:
        """Check if buffer has content."""
        return bool(self._buffer.strip())

@dataclass
class KokoroTTSOptions:
    """Configuration options for KokoroTTS."""
    model: str
    voice: TTSVoices | str
    speed: float


class KokoroTTS(tts.TTS):
    """TTS implementation using Kokoro API with streaming support and text buffering."""
    
    def __init__(
        self,
        base_url: str = "http://192.168.101.58:8880/v1",
        api_key: str = "not-needed",
        model: str = "kokoro",
        voice: TTSVoices | str = "echo",
        speed: float = 1.0,
        client: Optional[openai.AsyncClient] = None,
        buffer_sentences: bool = True,
        flush_timeout: float = 1.5,
        inter_chunk_pause: float = 1.5,  # Pause between TTS chunks in seconds
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=TTS_SAMPLE_RATE,
            num_channels=TTS_CHANNELS,
        )

        self._opts = KokoroTTSOptions(model=model, voice=voice, speed=speed)
        self._client = client or self._create_client(base_url, api_key)
        
        # Text buffering for more natural speech
        self._buffer_sentences = buffer_sentences
        self._text_buffer = TextBuffer(flush_timeout=flush_timeout) if buffer_sentences else None
        self._buffer_lock = asyncio.Lock() if buffer_sentences else None
        self._flush_task = None
        self._inter_chunk_pause = inter_chunk_pause

    def _create_client(self, base_url: str, api_key: str) -> openai.AsyncClient:
        """Create and configure OpenAI client."""
        return openai.AsyncClient(
            max_retries=0,
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=5.0, write=5.0, pool=5.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=50,
                    keepalive_expiry=120,
                ),
            ),
        )

    def update_options(
        self,
        *,
        model: NotGivenOr[str] = NOT_GIVEN,
        voice: NotGivenOr[TTSVoices | str] = NOT_GIVEN,
        speed: NotGivenOr[float] = NOT_GIVEN,
    ) -> None:
        """Update TTS options."""
        if is_given(model):
            self._opts.model = model
        if is_given(voice):
            self._opts.voice = voice
        if is_given(speed):
            self._opts.speed = speed

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "KokoroTTSChunkedStream":
        """Synthesize speech from text."""
        return KokoroTTSChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )

    def stream(self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        """Create a streaming interface for TTS synthesis."""
        if self._buffer_sentences:
            return KokoroTTSBufferedStreamingInterface(self, conn_options)
        else:
            return KokoroTTSStreamingInterface(self, conn_options)

    async def _synthesize_impl(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        options = None
    ) -> AsyncIterator[tts.SynthesizedAudio]:
        """Direct implementation for synthesis."""
        logger.info(f"?? _synthesize_impl called with text: '{text[:30]}{'...' if len(text) > 30 else ''}'")
        
        try:
            request_id = utils.shortuuid()
            
            # Create streaming request directly
            oai_stream = self._client.audio.speech.with_streaming_response.create(
                input=text,
                model=self._opts.model,
                voice=self._opts.voice,
                response_format="pcm",
                speed=self._opts.speed,
                timeout=httpx.Timeout(30, connect=DEFAULT_API_CONNECT_OPTIONS.timeout),
            )

            # Create audio byte stream for PCM conversion
            audio_bstream = utils.audio.AudioByteStream(
                sample_rate=TTS_SAMPLE_RATE,
                num_channels=TTS_CHANNELS,
            )

            # Process streaming audio data
            frame_count = 0
            async with oai_stream as stream:
                async for data in stream.iter_bytes():
                    for frame in audio_bstream.write(data):
                        frame_count += 1
                        logger.debug(f"?? Yielding audio frame {frame_count}: {len(frame.data)} bytes")
                        yield tts.SynthesizedAudio(
                            request_id=request_id,
                            segment_id=request_id,
                            frame=frame,
                            delta_text="",
                        )
                        
                # Flush remaining data
                for frame in audio_bstream.flush():
                    frame_count += 1
                    logger.debug(f"?? Yielding final frame {frame_count}: {len(frame.data)} bytes")
                    yield tts.SynthesizedAudio(
                        request_id=request_id,
                        segment_id=request_id,
                        frame=frame,
                        delta_text=text,
                    )
            
            if frame_count == 0:
                logger.warning("No audio frames generated in _synthesize_impl")
            else:
                logger.info(f"? _synthesize_impl generated {frame_count} audio frames")
                
        except Exception as e:
            logger.error(f"Kokoro TTS synthesis failed in _synthesize_impl: {e}")
            # Yield empty audio on error
            empty_frame = rtc.AudioFrame(
                data=b"",
                sample_rate=TTS_SAMPLE_RATE,
                num_channels=TTS_CHANNELS,
                samples_per_channel=0,
            )
            yield tts.SynthesizedAudio(
                request_id=utils.shortuuid(),
                segment_id=utils.shortuuid(),
                frame=empty_frame,
                delta_text=text,
            )

    async def aclose(self):
        """Clean up resources"""
        if self._client:
            await self._client.aclose()


class KokoroTTSStreamingInterface:
    """Streaming interface for Kokoro TTS."""
    
    def __init__(self, tts_impl: KokoroTTS, conn_options: APIConnectOptions):
        self._tts_impl = tts_impl
        self._conn_options = conn_options
        self._current_stream = None
        self._text_queue = asyncio.Queue()
        self._closed = False

    async def __aenter__(self):
        """Enter the streaming context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the streaming context."""
        self._closed = True

    def __aiter__(self):
        """Return self as async iterator."""
        return self

    async def __anext__(self):
        """Get next item from the stream."""
        while True:
            # If we have a current stream, try to get the next item from it
            if self._current_stream is not None:
                try:
                    result = await self._current_stream.__anext__()
                    return result
                except StopAsyncIteration:
                    self._current_stream = None
                    # Continue to check for more text
            
            # If we're closed and no current stream, stop iteration
            if self._closed:
                raise StopAsyncIteration
            
            # Wait for text to be available
            try:
                text = await asyncio.wait_for(self._text_queue.get(), timeout=10.0)
                
                # Create a new stream for this text
                self._current_stream = KokoroTTSChunkedStream(
                    tts=self._tts_impl,
                    input_text=text,
                    conn_options=self._conn_options,
                )
                # Continue to the next iteration to get audio from this stream
                
            except asyncio.TimeoutError:
                # No text available yet, but don't stop - keep waiting
                continue

    def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> "KokoroTTSChunkedStream":
        """Synthesize speech from text within the streaming context."""
        if voice is not None:
            self._tts_impl.update_options(voice=voice)
        if speed is not None:
            self._tts_impl.update_options(speed=speed)
            
        stream = KokoroTTSChunkedStream(
            tts=self._tts_impl,
            input_text=text,
            conn_options=self._conn_options,
        )
        
        self._current_stream = stream
        return stream

    def push_text(self, text: str):
        """Push text to the synthesis queue."""
        self._text_queue.put_nowait(text)

    async def apush_text(self, text: str):
        """Async push text to the synthesis queue."""
        await self._text_queue.put(text)


class KokoroTTSBufferedStreamingInterface:
    """Buffered streaming interface for Kokoro TTS that accumulates text into sentences."""
    
    def __init__(self, tts_impl: KokoroTTS, conn_options: APIConnectOptions):
        self._tts_impl = tts_impl
        self._conn_options = conn_options
        self._text_buffer = TextBuffer(flush_timeout=1.5)
        self._sentence_queue = asyncio.Queue()
        self._closed = False
        self._flush_task = None
        self._current_stream = None
        self._last_chunk_time = 0.0  # Track timing for inter-chunk pauses
        self._end_of_stream_marker = object()  # Sentinel value to signal end of stream
        self._last_activity_time = 0.0  # Track last text push or flush activity

    async def __aenter__(self):
        """Enter the streaming context."""
        # Start the flush monitoring task
        self._flush_task = asyncio.create_task(self._monitor_flush())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the streaming context."""
        self._closed = True
        
        # Flush any remaining text (tool calls are already filtered in push_text)
        remaining = self._text_buffer.flush()
        if remaining:
            logger.info(f"[FLUSH] Flushing remaining text on exit: '{remaining[:50]}...'")
            await self._sentence_queue.put(remaining)
        
        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Signal end of stream (the monitor task may have already done this)
        await self._sentence_queue.put(self._end_of_stream_marker)
        logger.info("[STREAM] TTS stream marked complete, closing...")

    def __aiter__(self):
        """Return self as async iterator."""
        return self

    async def __anext__(self):
        """Get next item from the stream."""
        import time
        
        while True:
            # If we have a current stream, try to get the next item from it
            if self._current_stream is not None:
                try:
                    result = await self._current_stream.__anext__()
                    return result
                except StopAsyncIteration:
                    # Mark the time when this chunk finished
                    self._last_chunk_time = time.time()
                    self._current_stream = None
                    # Continue to check for more sentences
            
            # Check if we need to add a pause between chunks
            current_time = time.time()
            if (self._last_chunk_time > 0 and 
                current_time - self._last_chunk_time < self._tts_impl._inter_chunk_pause):
                # Add natural pause between chunks
                pause_needed = self._tts_impl._inter_chunk_pause - (current_time - self._last_chunk_time)
                # logger.info(f"?? Adding {pause_needed:.1f}s pause between TTS chunks")
                await asyncio.sleep(pause_needed)
            
            # Wait for a complete sentence to be available
            # Use shorter timeout when closed to exit faster
            timeout = 0.5 if self._closed else 2.0
            try:
                sentence = await asyncio.wait_for(self._sentence_queue.get(), timeout=timeout)
                
                # Check for end-of-stream marker
                if sentence is self._end_of_stream_marker:
                    logger.info("[STREAM] End-of-stream marker received, stopping iteration")
                    raise StopAsyncIteration
                
                # Create a new stream for this sentence
                self._current_stream = KokoroTTSChunkedStream(
                    tts=self._tts_impl,
                    input_text=sentence,
                    conn_options=self._conn_options,
                )
                # Continue to the next iteration to get audio from this stream
                
            except asyncio.TimeoutError:
                # If closed and timed out, we're done
                if self._closed:
                    logger.info("[STREAM] Closed and no more sentences, stopping iteration")
                    raise StopAsyncIteration
                # Otherwise, keep waiting
                continue

    async def _monitor_flush(self):
        """Monitor buffer and flush incomplete sentences after timeout."""
        import time
        
        while not self._closed:
            await asyncio.sleep(0.1)  # Check every 100ms
            
            if self._text_buffer.should_flush():
                remaining = self._text_buffer.flush()
                if remaining:
                    logger.info(f"? Timeout flush: '{remaining[:50]}...'")
                    await self._sentence_queue.put(remaining)
                    self._last_activity_time = time.time()
            
            # Auto-complete stream if:
            # 1. Buffer is empty (no pending text)
            # 2. Some activity has occurred (text was processed)
            # 3. It's been >2s since last activity with no new text
            # 4. Stream not already closed
            current_time = time.time()
            if (not self._closed and 
                not self._text_buffer.has_content() and 
                self._last_activity_time > 0 and 
                (current_time - self._last_activity_time) > 2.0):
                logger.info("[STREAM] No new text for 2s after last activity, auto-completing stream")
                await self._sentence_queue.put(self._end_of_stream_marker)
                break  # Exit the monitor task

    def push_text(self, text: str):
        """Push text to the buffer and queue complete sentences for TTS."""
        import time
        
        # Check if this is a tool call - if so, discard it and signal stream completion immediately
        # Tool calls are mutually exclusive with text - a response is EITHER a tool call OR text
        if "$tool_calls" in text or "```tool_calls" in text or ('"function"' in text and '"args"' in text):
            logger.info(f"[DISCARD] Tool call detected in push_text, discarding: '{text[:50]}...'")
            logger.info("[STREAM] Tool call detected, immediately completing stream")
            
            # Flush any remaining text in buffer first
            if self._text_buffer.has_content():
                remaining = self._text_buffer.flush()
                if remaining and not ("```tool_calls" in remaining or '"function"' in remaining):
                    logger.info(f"[FLUSH] Flushing remaining text before tool call: '{remaining[:50]}...'")
                    self._sentence_queue.put_nowait(remaining)
            
            # Signal stream completion immediately
            self._sentence_queue.put_nowait(self._end_of_stream_marker)
            return
        
        # Update activity timestamp for normal text
        self._last_activity_time = time.time()
        
        # Add text to buffer and get any complete sentences
        complete_sentences = self._text_buffer.add_text(text)
        
        # Queue each complete sentence for TTS
        for sentence in complete_sentences:
            self._sentence_queue.put_nowait(sentence)

    async def apush_text(self, text: str):
        """Async push text to the buffer."""
        self.push_text(text)

    def clear_buffer(self):
        """Clear the text buffer without flushing. Used to discard unwanted text (e.g., tool calls)."""
        if self._text_buffer.has_content():
            discarded = self._text_buffer.flush()
            logger.info(f"[DISCARD] Cleared TTS buffer, discarded: '{discarded[:50]}...'")
            return discarded
        return None

    def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> "KokoroTTSChunkedStream":
        """Synthesize speech from text within the buffered streaming context."""
        if voice is not None:
            self._tts_impl.update_options(voice=voice)
        if speed is not None:
            self._tts_impl.update_options(speed=speed)
            
        # Add text to buffer instead of synthesizing immediately
        self.push_text(text)
        
        # Return a dummy stream - actual synthesis happens through the buffer
        return KokoroTTSChunkedStream(
            tts=self._tts_impl,
            input_text="",  # Empty since we're buffering
            conn_options=self._conn_options,
        )


class KokoroTTSChunkedStream(tts.ChunkedStream):
    """ChunkedStream implementation for KokoroTTS."""
    
    def __init__(
        self,
        *,
        tts: KokoroTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts: KokoroTTS = tts
        self._audio_generated = False

    async def _run(self, output_emitter: tts.AudioEmitter):
        """
        Generate audio using KokoroTTS and emit it through the output emitter.
        This follows the ChunkedStream pattern like KittenTTS.
        """
        if self._audio_generated:
            return

        stripped_text = self.input_text.strip()
        
        # Skip synthesis for empty text, punctuation-only, OR tool calls JSON
        if not stripped_text or stripped_text in ['.', ',', '!', '?', ';', ':', '\n', '\r\n']:
            logger.info(f"[SKIP] Skipping synthesis for punctuation/empty text: '{self.input_text}'")
            self._audio_generated = True
            return
        
        # Skip if this looks like tool calls JSON
        if "```tool_calls" in stripped_text or ('"function"' in stripped_text and '"args"' in stripped_text):
            logger.info(f"[SKIP] Skipping synthesis for tool calls JSON: '{stripped_text[:50]}...'")
            self._audio_generated = True
            return
        
        request_id = utils.shortuuid()
        emitter_initialized = False
        
        try:
            # Initialize output emitter - this should trigger agent_started_speaking
            output_emitter.initialize(
                request_id=request_id,
                sample_rate=TTS_SAMPLE_RATE,
                num_channels=TTS_CHANNELS,
                mime_type="audio/pcm",
            )
            emitter_initialized = True

            # Create streaming request
            oai_stream = self._tts._client.audio.speech.with_streaming_response.create(
                input=self.input_text,
                model=self._tts._opts.model,
                voice=self._tts._opts.voice,
                response_format="pcm",
                speed=self._tts._opts.speed,
                timeout=httpx.Timeout(30, connect=self._conn_options.timeout),
            )

            all_audio_data = b""
            async with oai_stream as stream:
                async for data in stream.iter_bytes():
                    all_audio_data += data
            
            if len(all_audio_data) == 0:
                logger.warning("No audio data received from Kokoro TTS server")
                return
            
            # Push the complete audio data as bytes
            output_emitter.push(all_audio_data)
            
            # Flush the emitter to indicate completion
            output_emitter.flush()
            
            self._audio_generated = True

        except openai.APITimeoutError as e:
            logger.error(f"Kokoro TTS timeout: {e}")
            raise APITimeoutError() from e
        except openai.APIStatusError as e:
            logger.error(f"Kokoro TTS API error: {e.status_code} - {e.message}")
            raise APIStatusError(
                e.message,
                status_code=e.status_code,
                request_id=e.request_id,
                body=e.body,
            ) from e
        except Exception as e:
            logger.error(f"KokoroTTS synthesis failed: {str(e)}")
            raise RuntimeError(f"KokoroTTS synthesis failed: {str(e)}")
        finally:
            # Only end input if the emitter was actually initialized
            if emitter_initialized:
                try:
                    output_emitter.end_input()
                except Exception as e:
                    logger.error(f"Error ending output emitter: {e}")