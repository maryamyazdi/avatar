import asyncio
import io
import logging
import wave
import aiohttp
from typing import Optional, AsyncIterator, Union
from dotenv import load_dotenv
from livekit.agents import (
    stt,
    utils,
)
from livekit.agents.utils import AudioBuffer


logger = logging.getLogger("whisper-endpoint-stt")


class WhisperEndpointSTT(stt.STT):
    """
    LiveKit STT plugin for connecting to the existing Whisper endpoint
    
    This plugin connects to the FastAPI Whisper service running on /whisper
    and provides both streaming and non-streaming speech-to-text capabilities.
    """
    
    def __init__(
        self,
        *,
        api_url: str = "http://192.168.101.58:8000",
        language: Optional[str] = "en",
        detect_language: bool = True,
        http_session: Optional[aiohttp.ClientSession] = None,
        streaming_chunk_duration: float = 2.0,  # seconds per chunk for streaming
        streaming_overlap: float = 0.5,  # seconds of overlap between chunks
    ):
        """
        Initialize the Whisper endpoint STT plugin
        
        Args:
            api_url: Base URL for the Whisper API endpoint
            language: Target language for transcription (e.g., 'fa', 'en')
            detect_language: Whether to auto-detect language
            http_session: Optional HTTP session for requests
            streaming_chunk_duration: Duration in seconds for each streaming chunk
            streaming_overlap: Overlap duration in seconds between streaming chunks
        """
        # Initialize with streaming capabilities
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False, 
                interim_results=False
            )
        )
        
        # self._api_url = api_url.rstrip("/")
        self._api_url = api_url
        self._language = language
        self._detect_language = detect_language
        self._http_session = http_session
        self._streaming_chunk_duration = streaming_chunk_duration
        self._streaming_overlap = streaming_overlap
        
        # Calculate frames per chunk based on typical 16kHz sample rate
        # Assuming 50ms per frame (800 samples at 16kHz)
        self._frames_per_chunk = int(streaming_chunk_duration * 20)  # 20 frames per second
        self._overlap_frames = int(streaming_overlap * 20)
        
        logger.info(f"Initialized WhisperEndpointSTT with API URL: {self._api_url}")

    async def _recognize_impl(
        self, 
        buffer: AudioBuffer, 
        *, 
        language: Optional[str] = "en",
        conn_options = None,
    ) -> stt.SpeechEvent:
        """
        Recognize speech from an audio buffer using the Whisper endpoint
        
        Args:
            buffer: Audio buffer containing the audio data
            language: Optional language override
            
        Returns:
            SpeechEvent with transcription results
        """
        try:
            # Merge audio frames into a single buffer
            merged_buffer = utils.merge_frames(buffer)
            
            # Convert to WAV format for the API
            wav_data = await self._buffer_to_wav(merged_buffer)
            
            # Send to Whisper endpoint
            result = await self._transcribe_audio(wav_data, language)
            
            # Parse and return result
            return await self._parse_transcription_result(result, language)
            
        except Exception as e:
            logger.error(f"Error in Whisper endpoint recognition: {e}")
            return self._create_empty_speech_event()

    async def _stream_recognize_impl(
        self,
        buffer: AsyncIterator,
        *,
        language: Optional[str] = "en",
        conn_options = None,
    ) -> AsyncIterator[stt.SpeechEvent]:
        """
        Stream recognition implementation - processes audio in chunks
        
        Args:
            buffer: Async iterator of audio frames
            language: Optional language override
            conn_options: Connection options (unused)
            
        Yields:
            SpeechEvent objects with interim and final transcriptions
        """
        audio_frames = []
        frame_count = 0
        
        try:
            async for audio_frame in buffer:
                audio_frames.append(audio_frame)
                frame_count += 1
                
                # Process when we have enough frames for a chunk
                if frame_count >= self._frames_per_chunk:
                    try:
                        # Merge frames into a buffer
                        chunk_buffer = utils.merge_frames(audio_frames)
                        
                        # Convert to WAV and transcribe
                        wav_data = await self._buffer_to_wav(chunk_buffer)
                        result = await self._transcribe_audio(wav_data, language)
                        
                        # Parse result and yield as interim transcript
                        event = await self._parse_transcription_result(result, language, is_interim=True)
                        if self._has_meaningful_content(event):
                            yield event
                        
                        # Keep overlap frames for next chunk
                        if self._overlap_frames > 0 and len(audio_frames) > self._overlap_frames:
                            audio_frames = audio_frames[-self._overlap_frames:]
                            frame_count = len(audio_frames)
                        else:
                            audio_frames = []
                            frame_count = 0
                        
                    except Exception as e:
                        logger.error(f"Error processing streaming chunk: {e}")
                        # Clear frames and continue on error
                        audio_frames = audio_frames[-10:] if len(audio_frames) > 10 else []
                        frame_count = len(audio_frames)
                        continue
            
            # Process any remaining frames as final transcript
            if len(audio_frames) > 5:  # Minimum frames for meaningful audio
                try:
                    final_buffer = utils.merge_frames(audio_frames)
                    wav_data = await self._buffer_to_wav(final_buffer)
                    result = await self._transcribe_audio(wav_data, language)
                    
                    event = await self._parse_transcription_result(result, language, is_interim=False)
                    if self._has_meaningful_content(event):
                        yield event
                        
                except Exception as e:
                    logger.error(f"Error processing final audio frames: {e}")
                    
        except Exception as e:
            logger.error(f"Error in stream recognition: {e}")
            yield self._create_empty_speech_event()

    async def _buffer_to_wav(self, buffer: AudioBuffer) -> bytes:
        """
        Convert AudioBuffer to WAV format bytes
        
        Args:
            buffer: AudioBuffer to convert
            
        Returns:
            WAV format audio data as bytes
        """
        io_buffer = io.BytesIO()
        
        with wave.open(io_buffer, "wb") as wav_file:
            wav_file.setnchannels(buffer.num_channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(buffer.sample_rate)
            wav_file.writeframes(buffer.data)
        
        return io_buffer.getvalue()

    async def _transcribe_audio(
        self, 
        audio_data: bytes, 
        language: Optional[str] = "en"
    ) -> dict:
        """
        Send audio to Whisper endpoint for transcription
        
        Args:
            audio_data: WAV format audio data
            language: Optional language code
            
        Returns:
            API response dictionary
        """
        session = self._http_session or aiohttp.ClientSession()
        
        try:
            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field(
                'file', 
                audio_data, 
                filename='audio.wav', 
                content_type='audio/wav'
            )
            
            # Use the single file transcription endpoint
            # url = f"{self._api_url}/transcribe_single/"
            
            url = self._api_url
            
            async with session.post(
                url,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Whisper endpoint error {response.status}: {error_text}")
                    return {}
                    
        except asyncio.TimeoutError:
            logger.error("Timeout while calling Whisper endpoint")
            return {}
        except Exception as e:
            logger.error(f"Error calling Whisper endpoint: {e}")
            return {}
        finally:
            if not self._http_session:
                await session.close()

    async def _parse_transcription_result(
        self, 
        result: dict, 
        language: Optional[str] = "en",
        is_interim: bool = False
    ) -> stt.SpeechEvent:
        """
        Parse transcription result from Whisper endpoint
        
        Args:
            result: API response dictionary
            language: Language code
            is_interim: Whether this is an interim result
            
        Returns:
            SpeechEvent with parsed transcription
        """
        try:
            # Handle different response formats
            if isinstance(result, list) and len(result) > 0:
                # Array format response
                transcription = result[0]
            elif isinstance(result, dict):
                # Direct dictionary format
                transcription = result
            else:
                return self._create_empty_speech_event()
            
            # Extract text from transcription
            text = ""
            if "text" in transcription:
                text = transcription["text"].strip()
            
            if not text:
                return self._create_empty_speech_event()
            
            # Determine event type
            event_type = (
                stt.SpeechEventType.INTERIM_TRANSCRIPT 
                if is_interim 
                else stt.SpeechEventType.FINAL_TRANSCRIPT
            )
            
            # Create speech data
            speech_data = stt.SpeechData(
                text=text,
                language=language or self._language or "auto"
            )
            
            logger.info(f"Transcribed ({'interim' if is_interim else 'final'}): {text}")
            
            return stt.SpeechEvent(
                type=event_type,
                alternatives=[speech_data],
            )
            
        except Exception as e:
            logger.error(f"Error parsing transcription result: {e}")
            return self._create_empty_speech_event()

    def _create_empty_speech_event(self) -> stt.SpeechEvent:
        """Create an empty speech event for error cases"""
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[],
        )

    def _has_meaningful_content(self, event: stt.SpeechEvent) -> bool:
        """Check if speech event has meaningful content"""
        return (
            event.alternatives and 
            len(event.alternatives) > 0 and 
            event.alternatives[0].text.strip()
        )

    async def aclose(self):
        """Clean up resources"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            logger.info("Closed HTTP session")
