"""
GPT-4o Realtime Audio Implementation using LangChain and OpenAI
Supports real-time audio input and output processing.
"""

import os
import pyaudio
import wave
import threading
import base64
import io
import tempfile
from typing import Optional, Callable, Dict, Any
import logging

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPT4oRealtimeAudio:
    """
    GPT-4o Realtime Audio processor using LangChain.
    Handles audio input recording, processing with GPT-4o-realtime, and audio output playback.
    """
    
    def __init__(
        self, 
        openai_api_key: Optional[str] = None,
        voice: str = "alloy",
        audio_format: str = "wav",
        sample_rate: int = 24000,
        chunk_size: int = 1024,
        channels: int = 1,
        temperature: float = 0.7
    ):
        """
        Initialize the GPT-4o Realtime Audio processor.
        
        Args:
            openai_api_key: OpenAI API key (if not provided, will use environment variable)
            voice: Voice for audio output ("alloy", "echo", "fable", "onyx", "nova", "shimmer")
            audio_format: Audio format ("wav", "mp3", "opus")
            sample_rate: Audio sample rate (Hz)
            chunk_size: Audio chunk size for processing
            channels: Number of audio channels
            temperature: Model temperature for responses
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it as parameter.")
        
        self.voice = voice
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.temperature = temperature
        
        # Audio processing components
        self.pyaudio_instance = pyaudio.PyAudio()
        self.is_recording = False
        self.is_playing = False
        self.recording_thread: Optional[threading.Thread] = None
        self.playback_thread: Optional[threading.Thread] = None
        
        # Initialize LangChain OpenAI model
        self._init_model()
        
        # Callbacks
        self.on_audio_received: Optional[Callable[[bytes], None]] = None
        self.on_response_received: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        logger.info(f"GPT-4o Realtime Audio initialized with voice: {voice}")
    
    def _init_model(self):
        """Initialize the ChatOpenAI model with realtime configuration."""
        try:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini-realtime-preview",
                temperature=self.temperature,
                openai_api_key=self.openai_api_key,
                model_kwargs={
                    "modalities": ["text", "audio"],
                    "audio": {
                        "voice": self.voice,
                        "format": self.audio_format
                    },
                }
            )
            logger.info("GPT-4o realtime model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GPT-4o realtime model: {e}")
            raise
    
    def record_audio(self, duration: float = 5.0, filename: Optional[str] = None) -> str:
        """
        Record audio from microphone.
        
        Args:
            duration: Recording duration in seconds
            filename: Output filename (if None, creates temporary file)
            
        Returns:
            Path to the recorded audio file
        """
        if filename is None:
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            filename = temp_file.name
            temp_file.close()
        
        try:
            # Configure audio stream
            stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            frames = []
            logger.info(f"Recording audio for {duration} seconds...")
            
            # Record audio
            for _ in range(0, int(self.sample_rate / self.chunk_size * duration)):
                data = stream.read(self.chunk_size)
                frames.append(data)
                
                if self.on_audio_received:
                    self.on_audio_received(data)
            
            # Stop and close stream
            stream.stop_stream()
            stream.close()
            
            # Save audio file
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio_instance.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))
            
            logger.info(f"Audio recorded and saved to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            if self.on_error:
                self.on_error(e)
            raise
    
    def start_continuous_recording(self):
        """Start continuous audio recording in a separate thread."""
        if self.is_recording:
            logger.warning("Recording is already in progress")
            return
        
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self._continuous_recording_loop)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        logger.info("Started continuous audio recording")
    
    def stop_continuous_recording(self):
        """Stop continuous audio recording."""
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        logger.info("Stopped continuous audio recording")
    
    def _continuous_recording_loop(self):
        """Continuous recording loop (runs in separate thread)."""
        try:
            stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            while self.is_recording:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    if self.on_audio_received:
                        self.on_audio_received(data)
                except Exception as e:
                    logger.error(f"Error in continuous recording: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logger.error(f"Error in continuous recording loop: {e}")
            if self.on_error:
                self.on_error(e)
    
    def process_audio_with_gpt4o(self, audio_file_path: str, prompt: str = "") -> Dict[str, Any]:
        """
        Process audio input with GPT-4o realtime model.
        
        Args:
            audio_file_path: Path to audio file
            prompt: Optional text prompt to accompany audio
            
        Returns:
            Response from GPT-4o model containing text and/or audio
        """
        try:
            # Read audio file
            with open(audio_file_path, "rb") as audio_file:
                audio_content = audio_file.read()
            
            # Encode audio as base64
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            
            # Prepare message content
            message_content = []
            
            # Add text prompt if provided
            if prompt:
                message_content.append({"type": "text", "text": prompt})
            
            # Add audio input
            message_content.append({
                "type": "input_audio", 
                "input_audio": {
                    "data": audio_base64,
                    "format": self.audio_format
                }
            })
            
            # Create message
            messages = [{"role": "user", "content": message_content}]
            
            logger.info("Sending audio to GPT-4o realtime model...")
            
            # Get response from model
            response = self.llm.invoke(messages)
            
            # Extract response data
            result = {
                "text_response": response.content if hasattr(response, 'content') else "",
                "audio_response": None,
                "full_response": response
            }
            
            # Check for audio response in additional_kwargs
            if hasattr(response, 'additional_kwargs') and response.additional_kwargs:
                audio_data = response.additional_kwargs.get('audio', {}).get('data')
                if audio_data:
                    result["audio_response"] = audio_data
            
            logger.info("Received response from GPT-4o realtime model")
            
            if self.on_response_received and result["text_response"]:
                self.on_response_received(result["text_response"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing audio with GPT-4o: {e}")
            if self.on_error:
                self.on_error(e)
            raise
    
    def play_audio_response(self, audio_base64: str, filename: Optional[str] = None) -> str:
        """
        Play audio response from GPT-4o.
        
        Args:
            audio_base64: Base64 encoded audio data
            filename: Optional filename to save audio (if None, creates temporary file)
            
        Returns:
            Path to the audio file that was played
        """
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_base64)
            
            # Create temporary file if filename not provided
            if filename is None:
                temp_file = tempfile.NamedTemporaryFile(suffix=f".{self.audio_format}", delete=False)
                filename = temp_file.name
                temp_file.close()
            
            # Save audio file
            with open(filename, 'wb') as f:
                f.write(audio_bytes)
            
            # Play audio file
            self._play_audio_file(filename)
            
            logger.info(f"Audio response played from: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error playing audio response: {e}")
            if self.on_error:
                self.on_error(e)
            raise
    
    def _play_audio_file(self, filename: str):
        """Play audio file using pyaudio."""
        try:
            # Read audio file
            wf = wave.open(filename, 'rb')
            
            # Create audio stream
            stream = self.pyaudio_instance.open(
                format=self.pyaudio_instance.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            
            # Play audio
            data = wf.readframes(self.chunk_size)
            while data:
                stream.write(data)
                data = wf.readframes(self.chunk_size)
            
            # Clean up
            stream.stop_stream()
            stream.close()
            wf.close()
            
        except Exception as e:
            logger.error(f"Error playing audio file: {e}")
            raise
    
    def start_conversation_loop(self, recording_duration: float = 5.0):
        """
        Start an interactive conversation loop.
        Records audio, processes with GPT-4o, and plays response.
        
        Args:
            recording_duration: Duration for each recording segment
        """
        logger.info("Starting interactive conversation loop. Press Ctrl+C to stop.")
        
        try:
            while True:
                input("Press Enter to start recording (or Ctrl+C to quit)...")
                
                # Record audio
                audio_file = self.record_audio(duration=recording_duration)
                
                try:
                    # Process with GPT-4o
                    response = self.process_audio_with_gpt4o(audio_file)
                    
                    # Print text response
                    if response["text_response"]:
                        print(f"GPT-4o Response: {response['text_response']}")
                    
                    # Play audio response if available
                    if response["audio_response"]:
                        self.play_audio_response(response["audio_response"])
                    else:
                        print("No audio response received.")
                    
                finally:
                    # Clean up temporary audio file
                    try:
                        os.unlink(audio_file)
                    except:
                        pass
                
        except KeyboardInterrupt:
            logger.info("Conversation loop stopped by user.")
        except Exception as e:
            logger.error(f"Error in conversation loop: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.stop_continuous_recording()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
            logger.info("GPT-4o Realtime Audio cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Example usage and testing
if __name__ == "__main__":
    try:
        # Create realtime audio processor
        realtime_audio = GPT4oRealtimeAudio(
            voice="alloy",
            temperature=0.7
        )
        
        # Example 1: Simple audio recording and processing
        print("=== Example 1: Record and Process Audio ===")
        audio_file = realtime_audio.record_audio(duration=5.0)
        response = realtime_audio.process_audio_with_gpt4o(
            audio_file, 
            prompt="Please respond to what I said and provide an audio response."
        )
        
        print(f"Text Response: {response['text_response']}")
        
        if response["audio_response"]:
            realtime_audio.play_audio_response(response["audio_response"])
        
        # Clean up
        os.unlink(audio_file)
        
        # Example 2: Interactive conversation loop
        print("\n=== Example 2: Interactive Conversation ===")
        realtime_audio.start_conversation_loop(recording_duration=3.0)
        
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'realtime_audio' in locals():
            realtime_audio.cleanup()
