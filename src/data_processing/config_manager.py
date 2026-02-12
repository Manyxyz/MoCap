import json
from pathlib import Path
from typing import Dict, Any
from ..config import (
    USER_SETTINGS_FILE, 
    DEFAULT_FRAME_RATE, 
    DEFAULT_CAMERA_DISTANCE, 
    GRID_SIZE, 
    GRID_SPACING, 
)


class ConfigManager:
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not ConfigManager._initialized:
            self.settings_file = USER_SETTINGS_FILE
            self.settings = self._load_settings()
            ConfigManager._initialized = True
    
    def _load_defaults(self) -> Dict[str, Any]:
        return {
            'frame_rate': float(DEFAULT_FRAME_RATE),
            'camera_distance': float(DEFAULT_CAMERA_DISTANCE),
            'grid_size': float(GRID_SIZE),
            'grid_spacing': float(GRID_SPACING),
        }
    
    def _load_settings(self) -> Dict[str, Any]:
        defaults = self._load_defaults()
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    user_settings = json.load(f)
                    
                merged = defaults.copy()
                merged.update(user_settings)
                
                
                return merged
                
            except Exception as e:
                
                return defaults
        else:
            
            return defaults
    
    def save_to_file(self):
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            
        except Exception as e:
            pass  
          
    def get(self, key: str, default=None) -> Any:
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any):
        self.settings[key] = value
        self.save_to_file()
    
    def update(self, new_settings: Dict[str, Any]):
        self.settings.update(new_settings)
        self.save_to_file()
    
    def get_all(self) -> Dict[str, Any]:
        return dict(self.settings)
    
    def reset_to_defaults(self):
        self.settings = self._load_defaults()
        self.save_to_file()