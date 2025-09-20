"""
PlantBox Streamlit Application
A multipage plant management application with three-column layout
"""

import streamlit as st
from dotenv import load_dotenv


def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="PlantBox",
        page_icon="🌱",
        layout="wide",
        initial_sidebar_state="expanded"
    )


def render_shared_right_sidebar():
    """Render shared right sidebar for all pages"""
    st.markdown("### Data Panel")
    st.markdown("---")
    st.info("Shared data representation panel")
    st.write("Common data components will be displayed here")
    
    # Placeholder sections for shared functionality
    st.subheader("System Status")
    st.success("System operational")
    
    st.subheader("Quick Stats")
    st.metric("Active Sessions", "1")
    st.metric("Data Points", "0")


def main():
    """Main application entry point"""
    setup_page_config()
    
    # Define pages
    camera_page = st.Page(
        "pages/camera_and_chat.py",
        title="Camera & Chat",
        icon="📸",
        default=True
    )
    
    sensors_page = st.Page(
        "pages/sensors.py",
        title="Sensors",
        icon="🌡️"
    )
    
    # Navigation using st.navigation (this will appear below the title)
    pg = st.navigation([camera_page, sensors_page])

    # Create shared layout with main content and right sidebar
    main_col, right_col = st.columns([4, 1])
    
    with right_col:
        render_shared_right_sidebar()
    
    with main_col:
        # Run the selected page in the main column
        pg.run()


if __name__ == "__main__":
    load_dotenv()
    main()
