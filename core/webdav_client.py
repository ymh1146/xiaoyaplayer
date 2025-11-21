from webdav4.client import Client
import urllib.parse

class WebDAVClient:
    """WebDAV客户端"""
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.client = Client(base_url, auth=(username, password))
        
        # 提取base_url的路径部分，用于后续路径处理
        parsed_base = urllib.parse.urlparse(base_url)
        self.base_path = urllib.parse.unquote(parsed_base.path.rstrip("/"))

    def _sanitize_path(self, path):
        """清理路径：移除base_path前缀并解码"""
        if not path:
            return ""
            
        path = urllib.parse.unquote(path)
            
        if self.base_path and path.startswith(self.base_path):
            if len(path) == len(self.base_path) or path[len(self.base_path)] == "/":
                return path[len(self.base_path):]
        return path

    def list_files(self, path):
        """列出指定路径下的文件"""
        try:
            clean_path = self._sanitize_path(path)
            items = self.client.ls(clean_path, detail=True)
            return items
        except Exception as e:
            print(f"WebDAV列表错误: {e}")
            return []

    def get_stream_url(self, path):
        """构造流媒体URL（包含认证信息）"""
        clean_path = self._sanitize_path(path)
        
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path
            
        base = self.base_url.rstrip("/")
        encoded_path = urllib.parse.quote(clean_path)
        full_url = f"{base}{encoded_path}"
        
        # 将认证信息添加到URL中供VLC使用
        parsed = urllib.parse.urlparse(full_url)
        safe_user = urllib.parse.quote(self.username)
        safe_pass = urllib.parse.quote(self.password)
        new_netloc = f"{safe_user}:{safe_pass}@{parsed.netloc}"
        
        final_url = urllib.parse.urlunparse((
            parsed.scheme,
            new_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return final_url
