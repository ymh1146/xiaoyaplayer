import httpx
import re
from urllib.parse import urlparse

class SearchClient:
    """小雅搜索客户端"""
    
    def __init__(self, webdav_url):
        """
        初始化搜索客户端
        
        Args:
            webdav_url: WebDAV服务器地址 (e.g. http://1.2.3.4:5678/dav)
        """
        # 从 WebDAV URL 提取 Base URL (去掉 /dav)
        parsed = urlparse(webdav_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        
    def search(self, keyword):
        """
        搜索视频文件
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            List[str]: 包含搜索结果路径的列表
        """
        url = f"{self.base_url}/search"
        params = {
            "box": keyword,
            "url": "",
            "type": "video"  # 只搜索视频
        }
        
        print(f"[DEBUG] Searching: {url} with params {params}")
        
        try:
            response = httpx.get(url, params=params, timeout=10)
            response.raise_for_status()
            return self._parse_results(response.text)
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            return []

    def _parse_results(self, html):
        """解析HTML搜索结果"""
        results = []
        # 正则匹配链接：<a ... href="/path" ...>text</a>
        # 兼容 href="/path" 和 href=/path (无引号)
        pattern = r'<a[^>]*href=["\']?([^"\'>\s]+)["\']?[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for href, text in matches:
            text = text.strip()
            
            # 过滤无效链接
            if not text or "返回" in text or "关注" in text:
                continue
                
            # 过滤非路径内容（路径通常包含 /）
            if '/' not in text:
                continue
                
            # 移除可能的HTML标签（如高亮）
            text = re.sub(r'<[^>]+>', '', text)
            
            # 解码URL编码（如果有）
            try:
                from urllib.parse import unquote
                text = unquote(text)
            except:
                pass
            
            results.append(text)
            
        return results
