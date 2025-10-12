import json
import os
from typing import Annotated

import requests
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field


class PlantRequirementsResult(BaseModel):
    """Always use this tool to structure your response to the user."""
    plant_name: str = Field(description="The name of the plant.")
    watering_frequency: float = Field(description="The watering frequency of the plant, unit in once per x days.")
    watering_amount: float = Field(description="The amount of water needed each time, unit in ml.")
    light_type: int = Field(description="The type of light required by the plant, 0 means no light needed, 1 means ultraviolet light, 2 means normal light. This field can be only 0, 1, or 2!")
    light_duration: float = Field(description="The light duration requirements of the plant, unit in x hours each day.")
    temperature: float = Field(description="The temperature requirements of the plant, unit in x degree Celsius.")
    fertilization_frequency: float = Field(description="Fertilization frequency of the plant, unit in once per x days. 0 means no fertilization needed.")
    fertilization_amount: float = Field(description="The amount of fertilizer needed each time, unit in ml.")
    wind: float = Field(description="Wind requirements of the plant, unit in x% power. Wind is powered by a small fan.")
    explain: str = Field(description="A brief explanation of the care requirements provided above.")


@tool
def firecrawl_search(query: Annotated[str, "Search query"], firecrawl_api_key: str) -> str:
    """Use this tool to search the web for relevant information."""

    url = "https://api.firecrawl.dev/v2/search"

    payload = {
        "query": query,
        "limit": 2,
        "sources": [
            "web"
        ],
        "timeout": 60000,
        "ignoreInvalidURLs": False,
        "scrapeOptions": {
            "formats": [
                "summary"
            ],
            "storeInCache": True,
            "waitFor": 0,
            "mobile": False,
            "skipTlsVerification": True,
            "removeBase64Images": True,
            "blockAds": True,
            "onlyMainContent": True
        }
    }

    headers = {
        'Content-Type': "application/json",
        'Authorization': f"Bearer {firecrawl_api_key}"
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers)
    result = response.json()

    if not result.get("success", False):
        raise ValueError(f"Search API request failed: {result.get("error")}")

    result = result.get("data", {})
    if not result.get("web"):
        return "No relevant information found."
    else:
        markdown = ""
        for page in result.get("web"):
            markdown += f"### From {page.get("title")} \n{page.get("summary")}\n\n"

        return markdown


class PlantRequirementsAgent:
    def __init__(self, api_key: str = None, base_url: str = None, firecrawl_api_key: str = None, model="gemini-2.5-flash"):
        self.firecrawl_api_key = firecrawl_api_key if firecrawl_api_key else os.getenv("FIRECRAWL_API_KEY")
        model = ChatOpenAI(base_url=base_url if base_url else os.getenv("OPENAI_API_BASE"),
                           api_key=api_key if api_key else os.getenv("OPENAI_API_KEY"),
                        model=model)
        self._model = model.bind_tools([firecrawl_search, PlantRequirementsResult])

    def get_requirements(self, plant_name: str, growth_stage: str) -> PlantRequirementsResult:
        messages = [
            {"role": "system",
             "content": """You are a helpful expert in plant that provides detailed plant care requirements based on the plant's name and growth stage. Use the provided web search tool to gather accurate and up-to-date information. If the input is not a plant, do not use the tool. Always respond with a JSON object containing the following keys: "plant_name", "watering_frequency", "watering_amount", "light_type", "light_duration", "temperature", "fertilization_frequency", "fertilization_amount", "wind", and "explain". The values should be specific and relevant to the plant's care needs."""},
            {"role": "user",
             "content": f"""Provide the care requirements for a plant named "{plant_name}" at its "{growth_stage}" growth stage. Use the web search tool to find relevant information if necessary."""},
        ]

        response = self._model.invoke(messages)

        # Handle tool calls if any
        if response.tool_calls:
            # Add the assistant's message with tool calls
            messages.append({"role": "assistant", "content": "", "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["args"])
                    }
                } for call in response.tool_calls
            ]})

            # Execute each tool call and add results
            for call in response.tool_calls:
                selected_tool = {"firecrawl_search": firecrawl_search}.get(call["name"])
                if selected_tool:
                    args = dict(call["args"])
                    args["firecrawl_api_key"] = self.firecrawl_api_key
                    tool_result = selected_tool.invoke(args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": tool_result
                    })

            # Get final response after tool execution
            response = self._model.invoke(messages)


            try:
                logger.debug(f"{response.tool_calls[0]["args"]}")
                if len(response.tool_calls) < 1:
                    return PlantRequirementsResult(plant_name="", watering_frequency=-1, watering_amount=-1, light_type=0, light_duration=-1, temperature=-1, fertilization_frequency=-1, fertilization_amount=-1, wind=-1, explain="")
                result = PlantRequirementsResult.model_validate(response.tool_calls[0]["args"], strict=True)
            except Exception as e:
                raise ValueError(f"Invalid response format: {e}")

            return result

        return PlantRequirementsResult(plant_name="", watering_frequency=-1, watering_amount=-1, light_type=0, light_duration=-1, temperature=-1, fertilization_frequency=-1, fertilization_amount=-1, wind=-1, explain="")


# if __name__ == "__main__":
#     from dotenv import load_dotenv
#     load_dotenv()
#     agent = PlantRequirementsAgent()
#     result = agent.get_requirements("Peanut", "Seed")
#     print(result)
