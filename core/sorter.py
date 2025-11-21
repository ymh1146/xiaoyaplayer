import re

class SmartSorter:
    """智能文件排序器"""
    @staticmethod
    def sort_files(files: list) -> list:
        """根据剧集编号排序文件"""
        return sorted(files, key=SmartSorter._get_sort_key)

    @staticmethod
    def _get_sort_key(file_item):
        """生成排序键值"""
        if isinstance(file_item, dict):
            filename = file_item.get('name', '')
        else:
            filename = str(file_item)
            
        # 优先级1: SxxExx 格式（如 S01E01）
        s_e_match = re.search(r'(?i)S(\d+)E(\d+)', filename)
        if s_e_match:
            season = int(s_e_match.group(1))
            episode = int(s_e_match.group(2))
            return (1, season, episode)
            
        # 优先级2: "第xx集" 格式
        ep_match = re.search(r'第(\d+)集', filename)
        if ep_match:
            episode = int(ep_match.group(1))
            return (2, 0, episode)
            
        # 优先级3: 文件名中的最后一个数字
        base_name = filename.rsplit('.', 1)[0]
        clean_name = re.sub(r'(19|20)\d{2}', '', base_name)  # 移除年份
        clean_name = re.sub(r'\d{3,4}p', '', clean_name)      # 移除分辨率
        
        nums = re.findall(r'\d+', clean_name)
        if nums:
            try:
                return (3, 0, int(nums[-1]))
            except ValueError:
                pass
                
        # 优先级4: 原始文件名
        return (4, 0, filename)

if __name__ == "__main__":
    # Test cases
    test_files = [
        "完美世界 - S01E01 - 第1集.mp4",
        "完美世界 - S01E10 - 第10集.mp4",
        "完美世界 - S01E2 - 第2集.mp4",
        "完美世界 - S01E100 - 第100集.mp4",
        "One Piece 1.mp4",
        "One Piece 11.mp4",
        "One Piece 2.mp4",
        "2021 Movie.mp4"
    ]
    
    sorted_files = SmartSorter.sort_files(test_files)
    print("Sorted files with keys:")
    for f in sorted_files:
        key = SmartSorter._get_sort_key(f)
        print(f"{f} -> {key}")
