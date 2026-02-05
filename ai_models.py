from openai import OpenAI
import json
import subprocess

class AIModel:
    """Base class for AI model interactions"""
    def __init__(self, name):
        self.name = name
    
    def generate_response(self, prompt):
        """Generate a response from the model"""
        raise NotImplementedError("Subclasses must implement this method")

class OpenAIModel(AIModel):
    """OpenAI model implementation"""
    def __init__(self):
        super().__init__("OpenAI")
        self.client = OpenAI(api_key="")
        self.model = "gpt-4.1-2025-04-14"
    
    def generate_response(self, prompt):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error with OpenAI model: {str(e)}"

class NebiusModel(AIModel):
    """Nebius AI model implementation"""
    def __init__(self):
        super().__init__("Nebius")
        self.client = OpenAI(
            base_url="https://api.studio.nebius.com/v1/",
            api_key=""
        )
        self.model = "openai/gpt-oss-120b"
    
    def generate_response(self, prompt):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error with Nebius model: {str(e)}"

class LlamaNebiusModel(AIModel):
    """Llama 3.3 70B model implementation using Nebius API"""
    def __init__(self):
        super().__init__("Llama 3.3")
        self.api_key = ""
        self.model = "meta-llama/Llama-3.3-70B-Instruct"
    
    def generate_response(self, prompt):
        try:
            curl_command = [
                'curl', 'https://api.studio.nebius.com/v1/chat/completions',
                '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-H', f'Authorization: Bearer {self.api_key}',
                '--data-binary', json.dumps({
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                    "temperature": 0.1
                })
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and result.stdout.strip():
                response_json = json.loads(result.stdout)
                if 'choices' in response_json and len(response_json['choices']) > 0:
                    return response_json['choices'][0]['message']['content']
            return f"Error with Llama model: {result.stderr}"
        except Exception as e:
            return f"Error with Llama model: {str(e)}"

class DeepseekModel(AIModel):
    """Deepseek AI model implementation"""
    def __init__(self):
        super().__init__("Deepseek")
        self.client = OpenAI(
            api_key="", 
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"
    
    def generate_response(self, prompt):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error with Deepseek model: {str(e)}"

class ClaudeModel(AIModel):
    """Claude AI model implementation"""
    def __init__(self):
        super().__init__("Claude")
        self.model = "claude-3-5-haiku-latest"
        self.api_key = ""
    
    def generate_response(self, prompt):
        try:
            curl_command = [
                'curl', 'https://api.anthropic.com/v1/messages',
                '-H', 'Content-Type: application/json',
                '-H', f'x-api-key: {self.api_key}',
                '-H', 'anthropic-version: 2023-06-01',
                '-d', json.dumps({
                    "model": self.model,
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}]
                })
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and result.stdout.strip():
                response_json = json.loads(result.stdout)
                if 'content' in response_json and len(response_json['content']) > 0:
                    return response_json['content'][0]['text']
            return f"Error with Claude model: {result.stderr}"
        except Exception as e:
            return f"Error with Claude model: {str(e)}"

class GeminiModel(AIModel):
    """Gemini AI model implementation using OpenAI compatibility layer"""
    def __init__(self):
        super().__init__("Gemini")
        self.client = OpenAI(
            api_key="",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.model = "gemini-2.0-flash"
    
    def generate_response(self, prompt):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."}, 
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error with Gemini model: {str(e)}"

# Model registry
AVAILABLE_MODELS = {
    "openai": OpenAIModel,
    "nebius": NebiusModel,
    "llama": LlamaNebiusModel,
    "deepseek": DeepseekModel,
    "claude": ClaudeModel,
    "gemini": GeminiModel
}

def get_model(model_name="openai"):
    """Get AI model instance by name"""
    model_class = AVAILABLE_MODELS.get(model_name.lower(), OpenAIModel)
    return model_class()