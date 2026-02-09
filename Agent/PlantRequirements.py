import base64
import json
import mimetypes
import os
from typing import Annotated, Union

import cv2
import numpy as np
import requests
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field


# =========================
# Result Schema
# =========================
class PlantRequirementsResult(BaseModel):
    plant_name: str = Field(description="The name of the plant.")
    watering_frequency: float = Field(description="Once per X days.")
    watering_amount: float = Field(description="Water amount per time (ml).")
    light_type: int = Field(
        description="0=no light, 1=UV, 2=normal light. Must be 0/1/2."
    )
    light_duration: float = Field(description="Light duration (hours/day).")
    temperature: float = Field(description="Temperature (°C).")
    fertilization_frequency: float = Field(description="Once per X days, 0 means no fertilization.")
    fertilization_amount: float = Field(description="Fertilizer amount (ml).")
    wind: float = Field(description="Wind power (%).")
    explain: str = Field(description="Brief explanation of care requirements.")


# =========================
# Tool: Firecrawl Search
# =========================
@tool
def firecrawl_search(query: Annotated[str, "Search query"]) -> str:
    """Search the web for plant care information."""

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set in environment variables.")

    url = "https://api.firecrawl.dev/v2/search"
    payload = {
        "query": query,
        "limit": 2,
        "sources": ["web"],
        "timeout": 60000,
        "scrapeOptions": {
            "formats": ["summary"],
            "onlyMainContent": True,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    result = response.json()

    if not result.get("success", False):
        raise ValueError(f"Firecrawl failed: {result.get('error')}")

    pages = result.get("data", {}).get("web", [])
    if not pages:
        return "No relevant information found."

    markdown = ""
    for page in pages:
        markdown += f"### {page.get('title')}\n{page.get('summary')}\n\n"

    return markdown


# =========================
# Agent
# =========================
class PlantRequirementsAgent:
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = "gpt-4o-mini",  # ⚠️ 如果你真用 Gemini，需要兼容 API
        enable_llm: bool = True,
    ):
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        resolved_base_url = base_url or os.getenv("OPENAI_API_BASE")

        # Allow project to start even if no API key is configured.
        if not enable_llm or not resolved_api_key:
            self._model = None
            return

        self._model = ChatOpenAI(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=model,
        ).bind_tools([firecrawl_search, PlantRequirementsResult])

    def get_requirements(
        self,
        plant_name: str,
        growth_stage: str,
        details: str,
        image_input: Union[str, np.ndarray],
    ) -> PlantRequirementsResult:
        if self._model is None:
            raise RuntimeError(
                "PlantRequirementsAgent LLM is disabled or OPENAI_API_KEY is not set. "
                "Set OPENAI_API_KEY to enable care requirement generation."
            )

        # ---------- Image handling ----------
        mime_type = "image/jpeg"

        if isinstance(image_input, str):
            if not os.path.isfile(image_input):
                raise FileNotFoundError(image_input)
            with open(image_input, "rb") as f:
                image_data = f.read()
            mime_type = mimetypes.guess_type(image_input)[0] or mime_type

        elif isinstance(image_input, np.ndarray):
            ok, buffer = cv2.imencode(".jpg", image_input)
            if not ok:
                raise ValueError("Failed to encode image")
            image_data = buffer.tobytes()

        else:
            raise TypeError("image_input must be str or np.ndarray")

        # ---------- Messages ----------
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a plant care expert. "
                    "Always return structured JSON using the provided schema."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f'Plant name: "{plant_name}"\n'
                            f"Growth stage: {growth_stage}\n"
                            f"Details: {details}"
                        ),
                    },
                    {
                        "type": "image",
                        "source_type": "base64",
                        "data": base64.b64encode(image_data).decode(),
                        "mime_type": mime_type,
                    },
                ],
            },
        ]

        response = self._model.invoke(messages)

        # ---------- Tool handling ----------
        if not response.tool_calls:
            logger.warning("No tool calls returned.")
            return PlantRequirementsResult(
                plant_name="",
                watering_frequency=-1,
                watering_amount=-1,
                light_type=0,
                light_duration=-1,
                temperature=-1,
                fertilization_frequency=-1,
                fertilization_amount=-1,
                wind=-1,
                explain="No valid response.",
            )

        logger.debug(response.tool_calls)

        try:
            args = response.tool_calls[0]["args"]
            return PlantRequirementsResult.model_validate(args, strict=True)
        except Exception as e:
            raise ValueError(f"Invalid model output: {e}")
