import base64
import mimetypes
import os

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError


class PlantRecognitionResult(BaseModel):
    """Always use this tool to structure your response to the user."""
    plant_name: str = Field(description="The name of the plant.")
    growth_stage: str= Field(description="The growth stage of the plant.")

class PlantRecognitionAgent:
    def __init__(self):
        model = ChatOpenAI(base_url=os.getenv("OPENAI_API_BASE"), api_key=os.getenv("OPENAI_API_KEY"),
                           model="gemini-2.5-flash")
        self._model = model.bind_tools([PlantRecognitionResult])

    def regocnize_plant(self, img_path: str) -> PlantRecognitionResult:
        if not os.path.isfile(img_path):
            raise FileNotFoundError(f"Image file not found: {img_path}")
        with open(img_path, "rb") as img_file:
            image_data = img_file.read()
            mime_type = mimetypes.guess_type(img_path)[0]
            if mime_type is None or not mime_type.startswith("image/"):
                raise ValueError("The provided file is not a valid image.")
        image_data = base64.b64encode(image_data).decode("utf-8")
        messages = [
            SystemMessage(
                """Identify the plant in the provided image and its current growth stage. Respond with a JSON object containing two keys: "plant_name" with the identified plant's common name as the value, and "growth_stage" with a description of the plant's current state (e.g., seedling, flowering, fruiting, dormant). Do not include any other text, explanation, or conversational content. The JSON object must be the sole output.\n"""),
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "Identify the plant and its growth stage in the image.",
                },
                {
                "type": "image",
                "source_type": "base64",
                "data": image_data,
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