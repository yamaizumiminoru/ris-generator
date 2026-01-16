import json
import os
import platform

APP_NAME = "RisGenerator"

def get_config_path():
    if platform.system() == "Windows":
        app_data = os.getenv("APPDATA")
        return os.path.join(app_data, APP_NAME, "config.json")
    else:
        # Fallback/Mac
        return os.path.join(os.path.expanduser("~"), ".risgenerator", "config.json")

def load_config() -> dict:
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(api_key: str, save_enabled: bool, model_name: str = "gemini-1.5-flash"):
    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    data = {"model_name": model_name}
    if save_enabled:
        data["api_key"] = api_key
        data["save_key"] = True
    else:
        data["save_key"] = False
        
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Failed to save config: {e}")
