"""
Camera & Chat Page
A page for camera functionality and chat interface
"""
import threading

import av
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from ultralytics import YOLO
from streamlit_chat import message
from legacy.agents.ChatAgent import ChatAgent

yolo_model_path = "resources/model/plantyolo.engine"

# Global model variable with thread lock
yolo_model = None
model_lock = threading.Lock()

# Thread-safe current frame storage
current_frame_storage = None
frame_lock = threading.Lock()

chat_agent = ChatAgent()

def set_current_frame(frame):
    """Thread-safe way to store the current frame"""
    global current_frame_storage
    with frame_lock:
        current_frame_storage = frame

def get_current_frame():
    """Thread-safe way to retrieve the current frame"""
    global current_frame_storage
    with frame_lock:
        return current_frame_storage

def load_yolo_model():
    """Load YOLO model with thread safety"""
    global yolo_model
    if yolo_model is None:
        with model_lock:
            if yolo_model is None:  # Double-check locking pattern
                try:
                    yolo_model = YOLO(yolo_model_path)
                    st.success("YOLO model loaded successfully!")
                except Exception as e:
                    st.error(f"Failed to load YOLO model: {e}")
                    # Fallback to a general model if plant model fails
    return yolo_model

def video_frame_callback(frame):
    """Process video frame with YOLO detection and return annotated frame"""
    # Convert frame to numpy array
    img = frame.to_ndarray(format="bgr24")
    
    # Store current frame using thread-safe storage
    set_current_frame(img)
    
    # Load model if not already loaded
    model = load_yolo_model()
    if model is None:
        return frame
    
    try:
        # Run YOLO detection and tracking
        results = model.track(img, persist=True, verbose=False)
        
        # Get the annotated frame
        if results and len(results) > 0:
            # Use the plot method to get annotated image
            annotated_img = results[0].plot()
        else:
            annotated_img = img
            
        # Convert back to VideoFrame
        return av.VideoFrame.from_ndarray(annotated_img, format="bgr24")
        
    except Exception as e:
        # In case of error, return original frame
        print(f"Error in YOLO processing: {e}")
        return frame

def render_main_content():
    """Render main content area for camera and chat"""
    st.header("📸 Camera & Chat")
    
    # Sync current frame from thread-safe storage to session state
    # This runs in the main Streamlit context where session state is available
    current_frame = get_current_frame()
    if current_frame is not None:
        st.session_state.current_frame = current_frame
    
    # Input section placeholder
    st.info("Remember to change the camera to PlantBox Camera")
    
    # YOLO Detection Controls
    detection_enabled = st.checkbox("Enable Object Detection", value=True)


    # WebRTC Streamer with YOLO callback
    webrtc_ctx = webrtc_streamer(
        key="plantbox_camera", 
        mode=WebRtcMode.SENDRECV,
        video_frame_callback=video_frame_callback if detection_enabled else None,
        media_stream_constraints={
            "video": {
                "width": {"min": 640, "ideal": 1280, "max": 1920},
                "height": {"min": 480, "ideal": 720, "max": 1080},
                "frameRate": {"min": 15, "ideal": 30, "max": 60}
            },
            "audio": False
        },
        async_processing=True,
    )

    
    # Chat section  
    st.subheader("Chat Interface")
    
    # Initialize session state for chat
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
        st.session_state.chat_messages.append({
            'message': 'Hello! I\'m your PlantBox AI assistant. How can I help you with your plants today?',
            'is_user': False,
            'key': 'initial'
        })
    
    def get_ai_response(user_input: str) -> str:
        """Generate AI response based on user input"""
        # Simple rule-based responses for plant-related queries
        return chat_agent.input_text(user_input)



    def on_input_change():
        """Handle user input change"""
        user_input = st.session_state.user_input
        if user_input.strip():
            # Add user message
            st.session_state.chat_messages.append({
                'message': user_input,
                'is_user': True,
                'key': f"user_{len(st.session_state.chat_messages)}"
            })
            
            # Generate and add AI response
            ai_response = get_ai_response(user_input)
            st.session_state.chat_messages.append({
                'message': ai_response,
                'is_user': False,
                'key': f"ai_{len(st.session_state.chat_messages)}"
            })
            
            # Clear input
            st.session_state.user_input = ""
    
    def clear_chat():
        """Clear chat history"""
        st.session_state.chat_messages = []
        st.session_state.chat_messages.append({
            'message': 'Hello! I\'m your PlantBox AI assistant. How can I help you with your plants today?',
            'is_user': False,
            'key': 'initial_new'
        })
    
    # Chat display container with fixed height
    chat_container = st.container(height=400)
    
    with chat_container:
        # Display all messages
        for i, msg in enumerate(st.session_state.chat_messages):
            message(
                msg['message'], 
                is_user=msg['is_user'], 
                key=f"chat_{i}_{msg['key']}"
            )
    
    # Chat controls
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.text_input(
            "Ask me about your plants...", 
            key="user_input",
            on_change=on_input_change,
            placeholder="e.g., How often should I water my plants?"
        )
    
    with col2:
        if st.button("Clear Chat", help="Clear all chat messages"):
            clear_chat()
            st.rerun()



def main():
    """Camera and chat page main function"""
    # Render main content (right sidebar is now shared in main.py)
    render_main_content()



# Run the page
main()
