"""支持 python -m cloud_music_mcp 运行"""

import sys
import os

# 确保正确的模块路径
_package_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_package_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from cloud_music_mcp.main import run_mcp

if __name__ == "__main__":
    run_mcp()