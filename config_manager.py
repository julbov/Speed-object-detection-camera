#!/usr/bin/env python3

import json
import os
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.config = {}
        self.lock = threading.Lock()
        self.callbacks = []
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logging.info(f"Configuration loaded from {self.config_file}")
            else:
                logging.error(f"Configuration file {self.config_file} not found")
                self.config = {}
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            self.config = {}
        
        return self.config
    
    def save_config(self) -> bool:
        try:
            with self.lock:
                # Add metadata
                self.config['_metadata'] = {
                    'last_updated': datetime.now().isoformat(),
                    'version': '1.0'
                }
                
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                
                logging.info(f"Configuration saved to {self.config_file}")
                
                # Notify callbacks
                for callback in self.callbacks:
                    try:
                        callback(self.config)
                    except Exception as e:
                        logging.error(f"Error in config callback: {e}")
                
                return True
        except Exception as e:
            logging.error(f"Error saving config: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        try:
            keys = key_path.split('.')
            value = self.config
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    if default is None:
                        logging.warning(f"Config key not found: {key_path}")
                    return default
            
            return value
        except Exception:
            return default
    
    def set(self, key_path: str, value: Any) -> bool:
        try:
            with self.lock:
                keys = key_path.split('.')
                config_ref = self.config
                
                # Navigate to the parent of the target key
                for key in keys[:-1]:
                    if key not in config_ref:
                        config_ref[key] = {}
                    config_ref = config_ref[key]
                
                # Set the value
                config_ref[keys[-1]] = value
                
                logging.info(f"Config updated: {key_path} = {value}")
                return True
        except Exception as e:
            logging.error(f"Error setting config {key_path}: {e}")
            return False
    
    def update_section(self, section: str, data: Dict[str, Any]) -> bool:
        try:
            with self.lock:
                if section not in self.config:
                    self.config[section] = {}
                
                self.config[section].update(data)
                logging.info(f"Config section updated: {section}")
                return True
        except Exception as e:
            logging.error(f"Error updating config section {section}: {e}")
            return False
    
    def get_all(self) -> Dict[str, Any]:
        return self.config.copy()
    
    def add_callback(self, callback):
        self.callbacks.append(callback)
    
    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

# Global configuration manager instance
config_manager = ConfigManager()

# Convenience functions for backward compatibility
def get_config(key_path: str, default: Any = None) -> Any:
    return config_manager.get(key_path, default)

def set_config(key_path: str, value: Any) -> bool:
    return config_manager.set(key_path, value)

def save_config() -> bool:
    return config_manager.save_config()

def reload_config() -> bool:
    return config_manager.load_config() 