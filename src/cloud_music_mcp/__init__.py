"""网易云音乐 MCP 服务器"""

import sys
import os

# 添加 src 目录到路径
_src_path = os.path.dirname(os.path.abspath(__file__))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# 导出主要功能（延迟导入避免循环依赖）
def get_mcp():
    """获取 MCP 服务器实例（延迟导入）"""
    from . import main
    return main.mcp

def run():
    """运行 MCP 服务器"""
    from . import main
    main.run()