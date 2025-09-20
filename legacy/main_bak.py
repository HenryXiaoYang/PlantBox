from dotenv import load_dotenv
from legacy.agents.PlantRecognition import PlantRecognitionAgent
from legacy.agents.PlantRequirements import PlantRequirementsAgent

if __name__ == "__main__":
    load_dotenv()
    recognizer = PlantRecognitionAgent()
    result = recognizer.regocnize_plant("resources/images/test.jpg")
    print("name=",result.plant_name,",stage=", result.growth_stage)

    requirement_agent = PlantRequirementsAgent()
    requirements = requirement_agent.get_requirements(result.plant_name, result.growth_stage)
    print(requirements)