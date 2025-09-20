import json
import os

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from .PlantRecognition import PlantRecognitionAgent
from .PlantRequirements import PlantRequirementsAgent
import streamlit as st

@tool
def plant_recognition() -> dict:
    """Recognizes the plant species and growth stage from the current camera frame. Returns a dictionary with 'plant' (species name) and 'growth_stage' keys. Returns 'unknown' values if no camera frame is available or plant cannot be identified."""
    recognizer = PlantRecognitionAgent()
    try:
        if hasattr(st.session_state, 'current_frame') and st.session_state.current_frame is not None:
            result = recognizer.regocnize_plant(st.session_state.current_frame)
            print(f"Recognized plant: {result.plant_name}, growth stage: {result.growth_stage}")
            return {"plant": result.plant_name, "growth_stage": result.growth_stage}
        else:
            print("Fucked")
            return {"plant": "unknown", "growth_stage": "unknown"}
    except Exception as e:
        # Handle any errors gracefully
        print(f"Error in plant recognition: {e}")
        return {"plant": "unknown", "growth_stage": "unknown"}

@tool
def plant_requirements(plant: str, growth_stage: str) -> dict:
    """
    Retrieves comprehensive care requirements for a specific plant at a given growth stage.

    Args:
        plant (str): The name or type of plant (e.g., "tomato", "rose", "fiddle leaf fig")
        growth_stage (str): The current growth phase of the plant (e.g., "seedling",
                           "vegetative", "flowering", "fruiting", "mature")

    Returns:
        dict: A comprehensive care guide containing:
            - water (str): Watering frequency and amount recommendations
            - light (str): Light requirements and optimal conditions
            - temperature (str): Ideal temperature range
            - humidity (str): Optimal humidity levels
            - soil (str): Soil type and composition requirements
            - fertilizer (str): Fertilization schedule and nutrient needs
            - explain (str): Additional care tips and explanations
    """
    agent = PlantRequirementsAgent()
    result = agent.get_requirements(plant, growth_stage)
    return {"water": result.water, "light": result.light, "temperature": result.temperature, "humidity": result.humidity, "soil": result.soil, "fertilizer": result.fertilizer, "explain": result.explain}


class ChatAgent:
    def __init__(self):

        model = ChatOpenAI(base_url=os.getenv("OPENAI_API_BASE"), api_key=os.getenv("OPENAI_API_KEY"),
                           model="gemini-2.5-flash")
        self._model = model.bind_tools([plant_recognition, plant_requirements])
        self._conversation = [{"role": "system", "content": "You are a helpful assistant for plant care. You can use the tools to recognize plants and get their care requirements."}]

    def input_text(self, content: str) -> str:
        self._conversation.append({"role": "user", "content": content})
         # Initial model invocation
        response = self._model.invoke(self._conversation)

        # Handle tool calls if any
        print(response.tool_calls)
        if response.tool_calls:
            # Add the assistant's message with tool calls
            self._conversation.append({"role": "assistant", "content": "", "tool_calls": [{
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["args"])
                    }
                } for call in response.tool_calls]})

            # Execute each tool call and add results
            for call in response.tool_calls:
                selected_tool = {"plant_recognition": plant_recognition, "plant_requirements": plant_requirements}.get(call["name"])
                if selected_tool:
                    tool_result = selected_tool.invoke(call["args"])
                    self._conversation.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": str(tool_result)
                    })

            # Get final response after tool execution
            response = self._model.invoke(self._conversation)

            self._conversation.append({"role": "assistant", "content": response.content})
        return response.content
