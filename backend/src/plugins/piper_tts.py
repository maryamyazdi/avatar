import logging

from livekit.agents import (
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
import httpx
import httpcore


logger = logging.getLogger("piper-tts")


# Piper typically uses 22050 Hz sample rate
TTS_SAMPLE_RATE = 22050
TTS_CHANNELS = 1

PIPER_BASE_URL = "http://192.168.101.58:8002"

class PiperTTS(tts.TTS):
    
    def __init__(
        self,
        *,
        base_url: str = PIPER_BASE_URL,
        sample_rate: int = TTS_SAMPLE_RATE,
    ) -> None:
        """
        Initialize Piper TTS.
        
        Args:
            base_url: Base URL for the Piper TTS API
            sample_rate: Audio sample rate
        """
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=TTS_CHANNELS,
        )

        self._base_url = base_url
        self._client = self._create_client()
        self._sample_rate = sample_rate

    def _create_client(self) -> httpx.AsyncClient:
        """Create HTTP client with appropriate timeouts."""
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=15.0, read=30.0, write=5.0, pool=5.0),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=120,
            ),
        )

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "PiperTTSChunkedStream":
        return PiperTTSChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )
    
    async def aclose(self):
        if self._client:
            await self._client.aclose()


class PiperTTSChunkedStream(tts.ChunkedStream):
    """ChunkedStream implementation for Piper TTS."""
    
    def __init__(
        self,
        *,
        tts: PiperTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts: PiperTTS = tts

    async def _run(self, output_emitter: tts.AudioEmitter):
        """
        Generate audio using Piper TTS and emit through the output emitter.
        """
        request_id = utils.shortuuid()
        emitter_initialized = False
        
        try:
            # Always initialize output emitter first
            output_emitter.initialize(
                request_id=request_id,
                sample_rate=self._tts._sample_rate,
                num_channels=TTS_CHANNELS,
                mime_type="audio/pcm",
            )
            emitter_initialized = True
            
            stripped_text = self.input_text.strip()
            if not stripped_text:
                logger.debug("Skipping empty text")
                return
            
            # Skip synthesis for punctuation-only text
            if stripped_text in ['.', ',', '!', '?', ';', ':', '\n', '\r\n']:
                logger.info(f"[SKIP] Skipping synthesis for punctuation-only text: '{self.input_text}'")
                return
            
            # Skip if this looks like tool calls JSON - check for common patterns
            if "$tool_calls" in stripped_text or "```tool_calls" in stripped_text or ('"function"' in stripped_text and '"args"' in stripped_text):
                logger.info(f"[SKIP] Skipping synthesis for tool calls JSON: '{stripped_text[:50]}...'")
                return

            all_audio_data = b""
            
            request_payload = {"text": self.input_text}
            
            async with self._tts._client.stream(
                'POST',
                '/stream',
                json=request_payload,
                timeout=httpx.Timeout(30.0, connect=self._conn_options.timeout),
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_msg = error_text.decode() if isinstance(error_text, bytes) else str(error_text)
                    logger.error(f"Piper TTS API error: {response.status_code} - {error_msg}")
                    raise APIStatusError(
                        f"Piper TTS API returned {response.status_code}: {error_msg}",
                        status_code=response.status_code,
                        request_id=request_id,
                        body=error_text,
                    )
                
                # Collect all audio data first (more reliable than incremental streaming)
                # This matches the API's approach of pre-generating all chunks
                try:
                    chunk_count = 0
                    async for data_chunk in response.aiter_bytes():
                        if data_chunk:
                            all_audio_data += data_chunk
                            chunk_count += 1
                    logger.debug(f"Received {chunk_count} chunks, {len(all_audio_data)} total bytes")
                except (httpcore.RemoteProtocolError, httpx.RemoteProtocolError) as e:
                    # Handle incomplete chunked reads
                    if len(all_audio_data) > 0:
                        logger.warning(
                            f"Connection closed early after receiving {len(all_audio_data)} bytes. "
                            f"Using partial audio data. Error: {e}"
                        )
                        # Continue with partial data - better than nothing
                    else:
                        # No data received at all, this is a real error
                        logger.error(f"Connection closed with no data received: {e}")
                        raise APIStatusError(
                            f"Piper TTS server connection error: {str(e)}",
                            status_code=500,
                            request_id=request_id,
                            body=None,
                        )
            
            # Check if we got any audio data
            if len(all_audio_data) == 0:
                error_msg = f"No audio data received from Piper TTS server for text: '{self.input_text[:100]}...'"
                logger.error(error_msg)
                raise APIStatusError(
                    error_msg,
                    status_code=500,
                    request_id=request_id,
                    body=None,
                )
            
            # Push the complete audio data as bytes
            logger.debug(f"Successfully received {len(all_audio_data)} bytes from Piper TTS")
            output_emitter.push(all_audio_data)
            
            # Flush the emitter to indicate completion
            output_emitter.flush()

        except httpx.TimeoutException as e:
            logger.error(f"Piper TTS timeout: {e}")
            raise APITimeoutError() from e
        except APIStatusError:
            raise
        except (httpcore.RemoteProtocolError, httpx.RemoteProtocolError) as e:
            # If we didn't catch it earlier, log and re-raise
            logger.error(f"Piper TTS connection error: {e}", exc_info=True)
            raise RuntimeError(f"Piper TTS connection closed prematurely: {str(e)}")
        except Exception as e:
            logger.error(f"Piper TTS synthesis failed: {e}", exc_info=True)
            raise RuntimeError(f"Piper TTS synthesis failed: {str(e)}")
        finally:
            if emitter_initialized:
                try:
                    output_emitter.end_input()
                except Exception as e:
                    logger.error(f"Error ending output emitter: {e}")

