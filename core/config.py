import json
import os

class Config:
    """配置管理类"""
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.data = {
            "webdav_url": "http://118.122.130.22:5678/dav",
            "username": "guest",
            "password": "guest_Api789",
            "skip_intro": 0,
            "skip_outro": 0,
            "volume": 100,
            "last_played_path": None,
            "last_played_time": 0
        }
        self.load()

    def load(self):
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
