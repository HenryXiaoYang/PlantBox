"""
Example usage of GPT-4o Realtime Audio implementation
"""

import os
import time
import asyncio
from typing import List, Dict, Any

from dotenv import load_dotenv
from realtime import GPT4oRealtimeAudio
from config import RealtimeConfig


def basic_example():
    """Basic example: Record audio, process with GPT-4o, and play response."""
    print("=== Basic GPT-4o Realtime Audio Example ===")
    
    try:
        # Load environment variables
        load_dotenv()
        
        # Create realtime audio processor
        realtime_audio = GPT4oRealtimeAudio(
            voice="alloy",
            temperature=0.7
        )
        
        print("Recording audio for 5 seconds. Please speak now...")
        
        # Record audio
        audio_file = realtime_audio.record_audio(duration=5.0)
        
        print("Processing audio with GPT-4o...")
        
        # Process with GPT-4o
        response = realtime_audio.process_audio_with_gpt4o(
            audio_file, 
            prompt="Please respond to what I said in a friendly and helpful manner."
        )
        
        # Display text response
        if response["text_response"]:
            print(f"GPT-4o Text Response: {response['text_response']}")
        
        # Play audio response
        if response["audio_response"]:
            print("Playing audio response...")
            realtime_audio.play_audio_response(response["audio_response"])
        else:
            print("No audio response received.")
        
        # Clean up
        os.unlink(audio_file)
        realtime_audio.cleanup()
        
        print("Basic example completed successfully!")
        
    except Exception as e:
        print(f"Error in basic example: {e}")


def interactive_conversation():
    """Interactive conversation example."""
    print("=== Interactive Conversation Example ===")
    print("This will start an interactive conversation with GPT-4o.")
    print("Press Enter to record audio, or type 'quit' to exit.")
    
    try:
        # Load configuration
        config = RealtimeConfig.from_env()
        
        # Create realtime audio processor with config
        realtime_audio = GPT4oRealtimeAudio(
            openai_api_key=config.openai_api_key,
            voice=config.model.voice,
            temperature=config.model.temperature,
            sample_rate=config.audio.sample_rate,
            chunk_size=config.audio.chunk_size,
            channels=config.audio.channels
        )
        
        conversation_history = []
        
        while True:
            user_input = input("\nPress Enter to record audio (or type 'quit' to exit): ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            
            print(f"Recording audio for {config.default_recording_duration} seconds...")
            
            # Record audio
            audio_file = realtime_audio.record_audio(
                duration=config.default_recording_duration
            )
            
            try:
                print("Processing with GPT-4o...")
                
                # Add conversation context
                context_prompt = ""
                if conversation_history:
                    context_prompt = "Previous conversation context: " + "; ".join(conversation_history[-3:]) + ". "
                
                # Process with GPT-4o
                response = realtime_audio.process_audio_with_gpt4o(
                    audio_file,
                    prompt=context_prompt + "Please respond naturally to what I said."
                )
                
                # Display and store text response
                if response["text_response"]:
                    print(f"\nGPT-4o: {response['text_response']}")
                    conversation_history.append(f"GPT-4o: {response['text_response']}")
                
                # Play audio response
                if response["audio_response"]:
                    print("Playing audio response...")
                    realtime_audio.play_audio_response(response["audio_response"])
                else:
                    print("No audio response received.")
                
            finally:
                # Clean up audio file
                try:
                    os.unlink(audio_file)
                except:
                    pass
        
        realtime_audio.cleanup()
        print("Conversation ended. Goodbye!")
        
    except Exception as e:
        print(f"Error in interactive conversation: {e}")


def continuous_recording_example():
    """Example with continuous audio recording and processing."""
    print("=== Continuous Recording Example ===")
    print("This example demonstrates continuous audio monitoring.")
    
    try:
        # Create realtime audio processor
        realtime_audio = GPT4oRealtimeAudio(voice="nova")
        
        # Audio buffer to collect chunks
        audio_buffer = []
        buffer_duration = 5.0  # Process every 5 seconds of audio
        chunks_per_buffer = int(buffer_duration * realtime_audio.sample_rate / realtime_audio.chunk_size)
        
        def on_audio_chunk_received(chunk: bytes):
            """Callback for when audio chunk is received."""
            audio_buffer.append(chunk)
            
            # Process when buffer is full
            if len(audio_buffer) >= chunks_per_buffer:
                print("Processing audio buffer...")
                
                # Save buffer to temporary file
                import tempfile
                import wave
                
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                filename = temp_file.name
                temp_file.close()
                
                # Write audio buffer to file
                with wave.open(filename, 'wb') as wf:
                    wf.setnchannels(realtime_audio.channels)
                    wf.setsampwidth(realtime_audio.pyaudio_instance.get_sample_size(pyaudio.paInt16))
                    wf.setframerate(realtime_audio.sample_rate)
                    wf.writeframes(b''.join(audio_buffer))
                
                try:
                    # Process with GPT-4o
                    response = realtime_audio.process_audio_with_gpt4o(
                        filename,
                        prompt="If you heard any speech, please respond. If it was just noise or silence, say 'I didn't hear anything clear.'"
                    )
                    
                    if response["text_response"]:
                        print(f"GPT-4o Response: {response['text_response']}")
                    
                    if response["audio_response"]:
                        realtime_audio.play_audio_response(response["audio_response"])
                
                finally:
                    # Clean up
                    try:
                        os.unlink(filename)
                    except:
                        pass
                    
                    # Clear buffer
                    audio_buffer.clear()
        
        # Set callback
        realtime_audio.on_audio_received = on_audio_chunk_received
        
        # Start continuous recording
        realtime_audio.start_continuous_recording()
        
        print("Continuous recording started. Speak to interact with GPT-4o.")
        print("Press Ctrl+C to stop.")
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping continuous recording...")
        
        realtime_audio.cleanup()
        print("Continuous recording example completed!")
        
    except Exception as e:
        print(f"Error in continuous recording example: {e}")


def voice_assistant_example():
    """Example of a voice assistant using GPT-4o realtime."""
    print("=== Voice Assistant Example ===")
    print("A simple voice assistant powered by GPT-4o realtime.")
    
    try:
        # Create voice assistant
        assistant = GPT4oRealtimeAudio(
            voice="nova",  # Use Nova voice for assistant
            temperature=0.8  # Slightly more creative
        )
        
        # Assistant greeting
        print("\nVoice Assistant: Hello! I'm your AI assistant. How can I help you today?")
        
        while True:
            user_input = input("\nSay 'record' to speak, or 'quit' to exit: ").strip().lower()
            
            if user_input in ['quit', 'exit', 'q']:
                break
            elif user_input == 'record':
                print("🎤 Recording for 6 seconds. Please speak your request...")
                
                # Record user request
                audio_file = assistant.record_audio(duration=6.0)
                
                try:
                    print("🤔 Processing your request...")
                    
                    # Process with assistant context
                    response = assistant.process_audio_with_gpt4o(
                        audio_file,
                        prompt="You are a helpful voice assistant. Please respond to the user's request in a natural, conversational way. Be concise but helpful."
                    )
                    
                    # Show text response
                    if response["text_response"]:
                        print(f"🤖 Assistant: {response['text_response']}")
                    
                    # Play audio response
                    if response["audio_response"]:
                        print("🔊 Playing response...")
                        assistant.play_audio_response(response["audio_response"])
                    else:
                        print("❌ No audio response received.")
                
                finally:
                    # Clean up
                    try:
                        os.unlink(audio_file)
                    except:
                        pass
            else:
                print("Please say 'record' or 'quit'.")
        
        assistant.cleanup()
        print("👋 Voice assistant session ended. Goodbye!")
        
    except Exception as e:
        print(f"Error in voice assistant: {e}")


def main():
    """Main function to run examples."""
    print("GPT-4o Realtime Audio Examples")
    print("=" * 40)
    
    examples = {
        "1": ("Basic Example", basic_example),
        "2": ("Interactive Conversation", interactive_conversation),
        "3": ("Continuous Recording", continuous_recording_example),
        "4": ("Voice Assistant", voice_assistant_example)
    }
    
    print("\nAvailable examples:")
    for key, (name, _) in examples.items():
        print(f"{key}. {name}")
    
    while True:
        choice = input("\nEnter example number (1-4) or 'quit' to exit: ").strip()
        
        if choice.lower() in ['quit', 'exit', 'q']:
            break
        elif choice in examples:
            name, func = examples[choice]
            print(f"\nRunning: {name}")
            print("-" * 40)
            func()
            print("-" * 40)
        else:
            print("Invalid choice. Please enter 1-4 or 'quit'.")
    
    print("Examples session ended.")


if __name__ == "__main__":
    main()


