"""
Configuration settings for GPT-4o Realtime Audio
"""

import os
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class AudioConfig:
    """Audio configuration settings."""
    sample_rate: int = 24000
    chunk_size: int = 1024
    channels: int = 1
    format: str = "wav"
    
    # Supported audio formats
    SUPPORTED_FORMATS = ["wav", "mp3", "opus"]
    
    def validate(self) -> bool:
        """Validate audio configuration."""
        if self.format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported audio format: {self.format}. Supported: {self.SUPPORTED_FORMATS}")
        if self.sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if self.chunk_size <= 0:
            raise ValueError("Chunk size must be positive")
        if self.channels <= 0:
            raise ValueError("Channels must be positive")
        return True


@dataclass
class ModelConfig:
    """GPT-4o model configuration settings."""
    model_name: str = "gpt-4o-realtime-preview"
    temperature: float = 0.7
    voice: str = "alloy"
    max_tokens: int = 4096
    
    # Supported voices
    SUPPORTED_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    
    def validate(self) -> bool:
        """Validate model configuration."""
        if self.voice not in self.SUPPORTED_VOICES:
            raise ValueError(f"Unsupported voice: {self.voice}. Supported: {self.SUPPORTED_VOICES}")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive")
        return True


@dataclass
class RealtimeConfig:
    """Complete configuration for GPT-4o Realtime Audio."""
    audio: AudioConfig
    model: ModelConfig
    openai_api_key: str
    openai_organization: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    
    # Recording settings
    default_recording_duration: float = 5.0
    max_recording_duration: float = 30.0
    
    # Logging
    log_level: str = "INFO"
    enable_debug: bool = False
    
    @classmethod
    def from_env(cls) -> 'RealtimeConfig':
        """Create configuration from environment variables."""
        # Load audio config
        audio_config = AudioConfig(
            sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "24000")),
            chunk_size=int(os.getenv("AUDIO_CHUNK_SIZE", "1024")),
            channels=int(os.getenv("AUDIO_CHANNELS", "1")),
            format=os.getenv("AUDIO_FORMAT", "wav")
        )
        
        # Load model config
        model_config = ModelConfig(
            model_name=os.getenv("OPENAI_MODEL", "gpt-4o-realtime-preview"),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            voice=os.getenv("OPENAI_VOICE", "alloy"),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
        )
        
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        config = cls(
            audio=audio_config,
            model=model_config,
            openai_api_key=api_key,
            openai_organization=os.getenv("OPENAI_ORGANIZATION", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            default_recording_duration=float(os.getenv("DEFAULT_RECORDING_DURATION", "5.0")),
            max_recording_duration=float(os.getenv("MAX_RECORDING_DURATION", "30.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            enable_debug=os.getenv("ENABLE_DEBUG", "false").lower() == "true"
        )
        
        config.validate()
        return config
    
    def validate(self) -> bool:
        """Validate complete configuration."""
        self.audio.validate()
        self.model.validate()
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
        
        if self.default_recording_duration <= 0:
            raise ValueError("Default recording duration must be positive")
        
        if self.max_recording_duration <= 0:
            raise ValueError("Max recording duration must be positive")
        
        if self.default_recording_duration > self.max_recording_duration:
            raise ValueError("Default recording duration cannot exceed max recording duration")
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "audio": {
                "sample_rate": self.audio.sample_rate,
                "chunk_size": self.audio.chunk_size,
                "channels": self.audio.channels,
                "format": self.audio.format
            },
            "model": {
                "model_name": self.model.model_name,
                "temperature": self.model.temperature,
                "voice": self.model.voice,
                "max_tokens": self.model.max_tokens
            },
            "openai": {
                "base_url": self.openai_base_url,
                "organization": self.openai_organization
            },
            "recording": {
                "default_duration": self.default_recording_duration,
                "max_duration": self.max_recording_duration
            },
            "logging": {
                "level": self.log_level,
                "debug": self.enable_debug
            }
        }


# Default configuration instance
DEFAULT_CONFIG = RealtimeConfig(
    audio=AudioConfig(),
    model=ModelConfig(),
    openai_api_key="",  # Must be set via environment or parameter
)


