import os
import requests

OLLAMA_MODELS = {
    "llama3.1", 
    "phi3",
    "deepseek-r1:1.5b"
}

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
) 

def prompt_model(model: str, prompt: str) -> str :
    """
    Prompt the model with the input prompt and return a text response. 
    It will select the model based on the input model. 
    
    Input: 
        - model: the name of the model to use, must be in OLLAMA_MODELS
        - prompt: the text prompt to send to the model
    Output: 
        - the text response from the model, or an error message if any issue occurs
    """
    if model not in OLLAMA_MODELS:
        return f"[Error] Unavailable model: {model}"

    try:
        # send a POST request to the Ollama server (send data)
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",      # Ollama’s inference endpoint
            json={
                "model": model,
                "prompt": prompt,
                "stream": False     # streaming not needed
            },
            timeout=120     # avoid freezing if model takes too long to respond
        )

        response.raise_for_status()     # check if the request was successful (status code 200-299), if not throws exception

        data = response.json()  # convert response to JSON format

        return data.get("response", "[Error] No response returned.")    # extract the "response" field from the JSON, if not present return error message

    except requests.exceptions.ConnectionError:     # if the connection to the Ollama server not running, or wrong port, or any other connection issue
        return "[Error] Cannot connect to Ollama server."

    except requests.exceptions.Timeout:
        return "[Error] Request timed out."

    except Exception as e:  # any other unexpected error 
        return f"[Error] {str(e)}"