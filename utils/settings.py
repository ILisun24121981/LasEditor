import os
import json


class SettingsManager:
    """Менеджер для сохранения и загрузки конфигураций приложения LasEditor из системной папки AppData."""

    APPDATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "LasEditor")
    SETTINGS_FILE = os.path.join(APPDATA_DIR, "config.json")

    @staticmethod
    def get_last_path():
        if os.path.exists(SettingsManager.SETTINGS_FILE):
            try:
                with open(SettingsManager.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("LasPath", "")
            except Exception: return ""
        return ""

    @staticmethod
    def set_last_path(path):
        try:
            if not os.path.exists(SettingsManager.APPDATA_DIR):
                os.makedirs(SettingsManager.APPDATA_DIR, exist_ok=True)
            config = SettingsManager.load_config()
            config["LasPath"] = path.replace("\\", "/")
            SettingsManager.save_config(config)
        except Exception: pass

    @staticmethod
    def load_config():
        if os.path.exists(SettingsManager.SETTINGS_FILE):
            try:
                with open(SettingsManager.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception: return {"LasPath": ""}
        return {"LasPath": ""}

    @staticmethod
    def save_config(config_data):
        try:
            if not os.path.exists(SettingsManager.APPDATA_DIR):
                os.makedirs(SettingsManager.APPDATA_DIR, exist_ok=True)
            with open(SettingsManager.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
        except Exception: pass
