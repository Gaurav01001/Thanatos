import ollama


class VisionModel:
    """Uses a local Ollama vision model to analyze images."""

    def __init__(self, model: str = "gemma3:4b"):
        self.model = model

    def analyze(self, image_path: str, prompt: str = "Describe what you see in this image.") -> str:
        """
        Send an image to the vision model and return its description.
        """

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_path],
                }
            ],
        )

        return response.message.content.strip()


if __name__ == "__main__":
    vision = VisionModel()

    image_path = input("Enter screenshot path: ").strip()

    result = vision.analyze(
        image_path,
        "Describe everything important you can see on this computer screen."
    )

    print("\nVision:")
    print(result)