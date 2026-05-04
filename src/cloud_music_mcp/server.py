"""Node.js API 代理服务器生命周期管理"""
import subprocess
import time
import os
import requests
import atexit

_API_PORT = 36530
_API_BASE = f"http://127.0.0.1:{_API_PORT}"
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_process = None


def _get_node_cmd():
    """获取启动 Node.js 代理的命令"""
    # 在项目根目录运行，使用本地 node_modules
    return [
        "node",
        "-e",
        "require('@neteasecloudmusicapienhanced/api').serveNcmApi({checkVersion:false,port:%d})" % _API_PORT,
    ]


def start():
    """启动 API 代理，阻塞直到就绪"""
    global _process

    if is_running():
        return _API_BASE

    proc = subprocess.Popen(
        _get_node_cmd(),
        cwd=_PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _process = proc

    # 轮询等待就绪
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Node.js 代理进程意外退出 (code={proc.returncode})")
        try:
            r = requests.get(f"{_API_BASE}/", timeout=2)
            if r.status_code == 200:
                atexit.register(stop)
                return _API_BASE
        except requests.RequestException:
            time.sleep(0.3)
    raise TimeoutError("API 代理启动超时")


def stop():
    """停止 API 代理"""
    global _process
    if _process:
        try:
            _process.terminate()
            _process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            _process.kill()
        _process = None


def is_running():
    """检查代理是否在运行"""
    try:
        r = requests.get(f"{_API_BASE}/", timeout=1)
        return r.status_code == 200
    except requests.RequestException:
        return False


def get_base():
    """获取 API 基础 URL"""
    return _API_BASE
