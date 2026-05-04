"""
Auth 模块 — 委托到 api.py
保留用于向后兼容，新代码请直接使用 api.py
"""
from cloud_music_mcp.api import (
    check_login_status,
    login_via_qrcode,
    clear_cookies as logout,
    load_cookies,
    save_cookies,
    get_current_login_status,
)

get_cookies = load_cookies
get_login_cookies = load_cookies


def load_session():
    """验证本地 session 有效性"""
    cookies = load_cookies()
    if not cookies.get('MUSIC_U'):
        return False, None, None
    try:
        user_info = get_current_login_status()
        if user_info and user_info.get("data", {}).get("code") == 200:
            profile = user_info["data"].get("profile", {})
            nickname = profile.get("nickname", "")
            return True, nickname, cookies
    except Exception:
        pass
    return False, None, None


def save_session(cookies):
    """保存 cookies"""
    return save_cookies(cookies)
