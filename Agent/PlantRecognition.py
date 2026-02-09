import base64
import mimetypes
import os
import io
from typing import Union

import cv2
import numpy as np
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

class PlantRecognitionResult(BaseModel):
    """Always use this tool to structure your response to the user."""
    plant_name: str = Field(description="The name of the plant.")
    details: str = Field(description="Additional details about the plant.")
    growth_stage: str= Field(description="The growth stage of the plant.")

class PlantRecognitionAgent:
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model="gemini-2.5-pro",
        enable_llm: bool = True,
    ):

        resolved_api_key = api_key if api_key else os.getenv("OPENAI_API_KEY")
        resolved_base_url = base_url if base_url else os.getenv("OPENAI_API_BASE")

        # Allow project to start even if no API key is configured.
        if not enable_llm or not resolved_api_key:
            self._model = None
            return

        model = ChatOpenAI(
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=model,
        )
        self._model = model.bind_tools([PlantRecognitionResult])

    def regocnize_plant(self, image_input: Union[str, np.ndarray]) -> PlantRecognitionResult:
        """
        Recognize plant from either file path or numpy array.
        
        Args:
            image_input: Either a file path (str) or numpy array (BGR format)
        """
        if isinstance(image_input, str):
            return self._recognize_from_path(image_input)
        elif isinstance(image_input, np.ndarray):
            return self._recognize_from_array(image_input)
        else:
            raise ValueError("Input must be either a file path (str) or numpy array")
    
    def _recognize_from_path(self, img_path: str) -> PlantRecognitionResult:
        """Recognize plant from file path"""
        if not os.path.isfile(img_path):
            raise FileNotFoundError(f"Image file not found: {img_path}")
        with open(img_path, "rb") as img_file:
            image_data = img_file.read()
            mime_type = mimetypes.guess_type(img_path)[0]
            if mime_type is None or not mime_type.startswith("image/"):
                raise ValueError("The provided file is not a valid image.")
        return self._process_image_data(image_data, mime_type or "image/jpeg")
    
    def _recognize_from_array(self, img_array: np.ndarray) -> PlantRecognitionResult:
        """Recognize plant from numpy array (BGR format)"""
        if len(img_array.shape) != 3 or img_array.shape[2] != 3:
            raise ValueError("Image array must be 3D with shape (height, width, 3)")
        
        # Encode as JPEG
        success, buffer = cv2.imencode('.jpg', img_array)
        if not success:
            raise ValueError("Failed to encode image array")
        
        image_data = buffer.tobytes()
        return self._process_image_data(image_data, "image/jpeg")
    
    def _process_image_data(self, image_data: bytes, mime_type: str) -> PlantRecognitionResult:
        """Process image data and get plant recognition result"""
        if self._model is None:
            raise RuntimeError(
                "PlantRecognitionAgent LLM is disabled or OPENAI_API_KEY is not set. "
                "Set OPENAI_API_KEY to enable recognition."
            )

        image_data_b64 = base64.b64encode(image_data).decode("utf-8")
        messages = [
            SystemMessage(
                """Identify the plant in the provided image and its current growth stage. Respond with a JSON object containing two keys: "plant_name" with the identified plant's common name as the value, "details" with additional information about the plant in the image, and "growth_stage" with a description of the plant's current state (e.g., seedling, flowering, fruiting, dormant). Do not include any other text, explanation, or conversational content. The JSON object must be the sole output.\n"""),
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "Identify the plant and its growth stage in the image.",
                },
                {
                "type": "image",
                "source_type": "base64",
                "data": image_data_b64,
                "mime_type": mime_type,
                }
                ],
            },
        ]

        response = self._model.invoke(messages)
        try:
            result = PlantRecognitionResult.model_validate(response.tool_calls[0]["args"], strict=True)
        except ValidationError as e:
            raise ValidationError(f"Invalid response format: {e}")
        return result