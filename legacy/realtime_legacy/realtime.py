import asyncio
import threading
import time
import uuid

from audio_manager import DialogSession

class Realtime:
    def __init__(self, app_id: str, access_key: str):
        ws_connect_config = {
            "base_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
            "headers": {
                "X-Api-App-ID": app_id,
                "X-Api-Access-Key": access_key,
                "X-Api-Resource-Id": "volc.speech.dialog",  # 固定值
                "X-Api-App-Key": "PlgvMymc7f3tQnJ6",  # 固定值
                "X-Api-Connect-Id": str(uuid.uuid4()),
            }
        }
        self.session = DialogSession(ws_config=ws_connect_config, output_audio_format="pcm", audio_file_path="")
        self._loop = None
        self.task = None
        self._thread = None
        
        # Start the session as a daemon
        self._start_daemon()

    def _start_daemon(self):
        """Start the asyncio event loop in a daemon thread."""
        def run_event_loop():
            # Create a new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            try:
                # Start the session task
                self.task = self._loop.create_task(self.session.start())
                print("Realtime processing started as daemon.")
                
                # Run the event loop until stopped
                self._loop.run_forever()
            except Exception as e:
                print(f"Error in daemon event loop: {e}")
            finally:
                # Clean up
                if self._loop and not self._loop.is_closed():
                    self._loop.close()

        # Create and start the daemon thread
        self._thread = threading.Thread(target=run_event_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the realtime session and daemon thread."""
        print("Stopping realtime processing...")
        
        if self._loop and self._loop.is_running():
            # Cancel the task
            if self.task and not self.task.done():
                self._loop.call_soon_threadsafe(self.task.cancel)
            
            # Stop the event loop
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        # Wait for thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        
        print("Realtime processing stopped.")

    def is_running(self):
        """Check if the daemon is running."""
        return (self._thread and self._thread.is_alive() and 
                self._loop and self._loop.is_running() and 
                self.task and not self.task.done())

    def input_text(self, text: str):
        """Input text to the dialog session."""
        if self.is_running():
            asyncio.run_coroutine_threadsafe(self.session.client.chat_text_query(content=text), self._loop)
        else:
            print("Realtime session is not running. Cannot input text.")

    def start_microphone(self):
        """Start microphone input."""
        if self.is_running():
            asyncio.run_coroutine_threadsafe(self.session.process_microphone_input_no_hello(), self._loop)
        else:
            print("Realtime session is not running. Cannot start microphone.")

    def stop_microphone(self):
        """Stop microphone input."""
        if self.is_running():
            self.session.is_recording = False
        else:
            print("Realtime session is not running. Cannot stop microphone.")


realtime = Realtime(app_id="3767790159", access_key="BOvf-toIvS27LfPmQX1mAUklhEhlwHSv")
time.sleep(5)
realtime.input_text("今天天气怎么样")
realtime.start_microphone()
time.sleep(5)
realtime.stop_microphone()
while True:
    time.sleep(1)