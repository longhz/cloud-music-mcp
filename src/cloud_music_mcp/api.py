#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
网易云音乐 MCP - 核心 API 模块
通过本地 Node.js API 代理 (localhost:36530) 调用网易云音乐 API
代理负责 WEPI 加密，Python 端只做 HTTP 转发
"""

import os
import json
import time
import base64
import requests
from pathlib import Path


# ==================== 常量 ====================

PROXY_BASE = "http://127.0.0.1:36530"
STORAGE_DIR = Path(__file__).parent / "storage"
COOKIE_FILE = STORAGE_DIR / "cookies.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "CloudMusic"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
IPHONE_UA = "NeteaseMusic 9.0.90/5038 (iPhone; iOS 16.2; zh_CN)"

# 音质等级体系（与网易云客户端对齐）
QUALITY_LEVELS = {
    "standard":  {"label": "标准",     "br": "128kbps"},
    "higher":    {"label": "较高",     "br": "192kbps"},
    "exhigh":    {"label": "极高",     "br": "320kbps"},
    "lossless":  {"label": "无损",     "br": "~900kbps"},
    "hires":     {"label": "Hi-Res",   "br": "~2000kbps"},
    "jyeffect":  {"label": "高清环绕声", "br": "~4000kbps"},
    "sky":       {"label": "沉浸环绕声", "br": "~4000kbps"},
    "dolby":     {"label": "杜比全景声", "br": "~6000kbps"},
    "jymaster":  {"label": "超清母带",  "br": "~6000kbps"},
}

# 高级音质需模拟 iPhone 请求
_ADVANCED_QUALITIES = {"jyeffect", "sky", "dolby", "jymaster"}

# 懒加载代理
_proxy_started = False


def _ensure_proxy():
    """确保 Node.js API 代理在运行"""
    global _proxy_started
    if _proxy_started:
        return
    try:
        from cloud_music_mcp.server import start
        start()
        _proxy_started = True
    except Exception:
        pass  # main.py 会在启动时就处理好


# ==================== Cookie 管理 ====================

def ensure_storage_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def load_cookies():
    ensure_storage_dir()
    if COOKIE_FILE.exists():
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cookies(cookies):
    ensure_storage_dir()
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, indent=2)


def build_cookie_string():
    """构建认证 Cookie 字符串"""
    cookies = load_cookies()
    keys = ['MUSIC_U', 'MUSIC_A_T', 'MUSIC_R_T', '__csrf']
    return '; '.join(f"{k}={cookies[k]}" for k in keys if k in cookies)


def clear_cookies():
    ensure_storage_dir()
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()
    return True


def _parse_set_cookie(response):
    """从响应头提取 Set-Cookie 并更新本地存储"""
    set_cookie = response.headers.get('Set-Cookie', '')
    if not set_cookie:
        return
    cookies = load_cookies()
    updated = False
    for part in set_cookie.split(','):
        # MUSIC_U=xxx; Max-Age=...; Path=/; HTTPOnly
        for item in part.split(';'):
            item = item.strip()
            if '=' in item:
                k, v = item.split('=', 1)
                auth_keys = ['MUSIC_U', 'MUSIC_A_T', 'MUSIC_R_T', '__csrf', 'NMTID']
                if k in auth_keys:
                    cookies[k] = v
                    updated = True
    if updated:
        save_cookies(cookies)


def parse_cookie_string(cookie_str):
    """解析分号分隔的 cookie 字符串为 dict"""
    result = {}
    for part in cookie_str.split(';'):
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            result[k] = v
    return result


# ==================== HTTP 请求层 ====================

def _get(url, params=None, auth=True, timeout=10, extra_headers=None):
    """GET 请求到代理"""
    _ensure_proxy()
    headers = {
        "User-Agent": UA,
        "Referer": "https://music.163.com/",
    }
    if auth:
        cookie_str = build_cookie_string()
        if cookie_str:
            headers["Cookie"] = cookie_str
    if extra_headers:
        headers.update(extra_headers)

    resp = requests.get(f"{PROXY_BASE}{url}", params=params, headers=headers, timeout=timeout)
    _parse_set_cookie(resp)
    return resp.json()


def _post(url, data=None, auth=True, timeout=10):
    """POST 请求到代理"""
    _ensure_proxy()
    headers = {
        "User-Agent": UA,
        "Referer": "https://music.163.com/",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if auth:
        cookie_str = build_cookie_string()
        if cookie_str:
            headers["Cookie"] = cookie_str

    resp = requests.post(f"{PROXY_BASE}{url}", data=data, headers=headers, timeout=timeout)
    _parse_set_cookie(resp)
    return resp.json()


# ==================== 登录相关 ====================

def get_qrcode_key():
    """获取二维码 key"""
    ts = int(time.time() * 1000)
    result = _get("/login/qr/key", params={"timestamp": ts, "type": 1}, auth=False)
    data = result.get("data", result)
    return data


def create_qrcode(key):
    """获取二维码图片 base64"""
    ts = int(time.time() * 1000)
    result = _get("/login/qr/create", params={"key": key, "qrimg": True, "timestamp": ts}, auth=False)
    data = result.get("data", result)
    return data


def check_qrcode_status(key):
    """检查二维码扫码状态"""
    ts = int(time.time() * 1000)
    result = _get("/login/qr/check", params={"key": key, "timestamp": ts}, auth=False)
    return result


def get_current_login_status():
    """获取当前登录状态"""
    ts = int(time.time() * 1000)
    try:
        return _get("/login/status", params={"timestamp": ts})
    except Exception:
        return None


def check_login_status():
    """检查登录状态（高层封装）"""
    cookies = load_cookies()
    if not cookies.get('MUSIC_U'):
        return {"logged_in": False, "nickname": None}

    try:
        resp = get_current_login_status()
        if resp and resp.get("data", {}).get("code") == 200:
            profile = resp["data"].get("profile", {})
            return {
                "logged_in": True,
                "nickname": profile.get("nickname", "用户"),
            }
    except Exception:
        pass

    return {"logged_in": False, "nickname": None}


def login_via_qrcode():
    """完整的扫码登录流程，返回 (success, message, nickname)"""
    import qrcode as qr
    from PIL import Image

    try:
        # 1. 获取 key
        result = get_qrcode_key()
        if result.get("code") != 200:
            return {"success": False, "message": f"获取二维码失败: {result.get('message', '未知')}"}

        key = result.get("unikey", "")
        if not key:
            return {"success": False, "message": "获取 unikey 失败"}

        # 2. 生成并弹出二维码
        qr_content = f"https://music.163.com/login?codekey={key}"
        img = qr.make(qr_content)
        ensure_storage_dir()
        qr_path = STORAGE_DIR / "login_qrcode.png"
        img.save(str(qr_path))

        import sys, subprocess
        if sys.platform == "win32":
            os.startfile(str(qr_path))
        else:
            subprocess.run(["open", str(qr_path)])

        # 3. 轮询
        for _ in range(60):
            result = check_qrcode_status(key)
            code = result.get("code", -1)

            if code == 800:
                return {"success": False, "message": "二维码已过期"}
            elif code == 803:
                cookie_str = result.get("cookie", "")
                if cookie_str:
                    cookie_dict = parse_cookie_string(cookie_str)
                    save_cookies(cookie_dict)

                status = check_login_status()
                return {
                    "success": True,
                    "message": f"登录成功! {status['nickname']}",
                    "nickname": status["nickname"],
                }
            time.sleep(2)

        return {"success": False, "message": "登录超时"}

    except Exception as e:
        return {"success": False, "message": f"错误: {e}"}


# ==================== 歌单相关 ====================

def get_user_playlists():
    """获取用户歌单"""
    status = check_login_status()
    if not status["logged_in"]:
        return {"success": False, "playlists": [], "error": "未登录"}

    ts = int(time.time() * 1000)
    # 先获取用户信息拿到 uid
    login_info = get_current_login_status()
    uid = None
    if login_info and login_info.get("data", {}).get("profile"):
        uid = login_info["data"]["profile"].get("userId")
    if not uid:
        return {"success": False, "playlists": [], "error": "无法获取用户ID"}

    result = _get("/user/playlist", params={"uid": str(uid), "timestamp": ts, "limit": 50})
    data = result.get("data", result)

    if data.get("code") == 200 and "playlist" in data:
        playlists = []
        for pl in data["playlist"]:
            playlists.append({
                "id": pl.get("id"),
                "name": pl.get("name", ""),
                "count": pl.get("trackCount", 0),
                "creator": pl.get("creator", {}).get("nickname", ""),
                "is_mine": pl.get("creator", {}).get("userId") == uid,
            })
        return {"success": True, "playlists": playlists}

    return {"success": False, "playlists": [], "error": str(data)}


def get_playlist_detail(playlist_id):
    """获取歌单详情"""
    ts = int(time.time() * 1000)
    result = _get("/playlist/detail", params={"id": str(playlist_id), "timestamp": ts})
    data = result.get("data", result)

    if data.get("code") == 200 and "playlist" in data:
        pl = data["playlist"]
        tracks = pl.get("tracks", [])
        songs = []
        for t in tracks:
            artists = [ar.get("name", "") for ar in t.get("ar", [])]
            songs.append({
                "id": t.get("id"),
                "name": t.get("name", ""),
                "artist": ", ".join(a for a in artists if a),
                "album": t.get("al", {}).get("name", ""),
            })
        return {
            "success": True,
            "info": {
                "id": pl.get("id"),
                "name": pl.get("name", ""),
                "creator": pl.get("creator", {}).get("nickname", ""),
                "count": pl.get("trackCount", 0),
            },
            "songs": songs,
        }
    return {"success": False, "error": str(data)}


def get_playlist_all(playlist_id, limit=200):
    """获取歌单所有歌曲"""
    ts = int(time.time() * 1000)
    result = _get("/playlist/track/all", params={"id": str(playlist_id), "limit": limit, "timestamp": ts})
    data = result.get("data", result)

    if data.get("code") == 200 and "songs" in data:
        songs = []
        for t in data["songs"]:
            artists = [ar.get("name", "") for ar in t.get("ar", [])]
            songs.append({
                "id": t.get("id"),
                "name": t.get("name", ""),
                "artist": ", ".join(a for a in artists if a),
                "album": t.get("al", {}).get("name", ""),
            })
        return {"success": True, "songs": songs}
    return {"success": False, "error": str(data)}


# ==================== 歌曲相关 ====================

def get_song_detail(ids):
    """获取歌曲详情"""
    if isinstance(ids, list):
        ids = ','.join(map(str, ids))
    ts = int(time.time() * 1000)
    result = _get("/song/detail", params={"ids": str(ids), "timestamp": ts})
    return result


def get_music_url(song_id, level='lossless'):
    """获取播放/下载 URL（高级音质自动使用 iPhone UA 请求头）"""
    ts = int(time.time() * 1000)
    extra = {}
    if level in _ADVANCED_QUALITIES:
        extra = {
            "User-Agent": IPHONE_UA,
            "Cookie": "os=iPhone OS; appver=9.0.90; osver=16.2; channel=distribution",
        }
    result = _get("/song/url/v1", params={"id": str(song_id), "level": level, "timestamp": ts},
                  extra_headers=extra if extra else None)
    return result


def get_lyric(song_id):
    """获取歌词"""
    ts = int(time.time() * 1000)
    result = _get("/lyric", params={"id": str(song_id), "timestamp": ts})
    return result


def check_music(song_id):
    """检查歌曲是否可用"""
    ts = int(time.time() * 1000)
    result = _get("/check/music", params={"id": str(song_id), "timestamp": ts})
    return result


def get_vip_info():
    """获取 VIP 信息（会员类型、等级、到期时间等）

    vipCode 说明:
        100 = 音乐包, 220 = 黑胶VIP音乐包
        300 = 黑胶SVIP, 600 = 家庭VIP
    """
    ts = int(time.time() * 1000)
    result = _get("/vip/info", params={"timestamp": ts})
    # 同时获取用户等级
    try:
        level_result = _get("/user/level", params={"timestamp": ts})
        result["_level"] = level_result
    except Exception:
        pass
    return result


def download_song(song_id, level="lossless", save_dir=None):
    """
    下载歌曲到本地

    Args:
        song_id: 歌曲ID
        level: 音质等级 (standard/higher/exhigh/lossless/hires/jyeffect/sky/dolby/jymaster)
        save_dir: 保存目录（默认 ~/Downloads/CloudMusic/）

    Returns:
        dict: {success, path, filename, size_mb, bitrate, quality, message}
    """
    if save_dir is None:
        save_dir = DEFAULT_DOWNLOAD_DIR
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取歌曲详情（用于构建文件名）
    detail = get_song_detail([song_id])
    detail_data = detail.get("data", detail)
    song_name = ""
    artist_name = ""
    if detail_data.get("code") == 200 and "songs" in detail_data:
        song = detail_data["songs"][0]
        song_name = song.get("name", "unknown")
        artists = [ar.get("name", "") for ar in song.get("ar", [])]
        artist_name = ", ".join(artists)

    # 2. 检查歌曲是否可用
    check = check_music(song_id)
    check_data = check.get("data", check)
    if check_data.get("code") != 200:
        return {"success": False, "message": "歌曲不可用（版权/下架）"}

    # 3. 获取下载 URL（含音质回退逻辑）
    url_result = get_music_url(song_id, level)
    url_items = url_result.get("data", url_result)  # data 是数组 [{id, url, br, level, ...}]

    actual_level = level
    download_url = None
    actual_br = 0

    # 从返回的数组中找第一个有 url 的项
    if isinstance(url_items, list):
        for item in url_items:
            if item.get("url") and item.get("code") == 200:
                download_url = item["url"]
                actual_br = item.get("br", 0)
                actual_level = item.get("level", level) or level
                break

    # 高级音质回退：如果没拿到，尝试线性回退
    if not download_url:
        fallback_chain = ["hires", "lossless", "exhigh", "higher", "standard"]
        for fallback in fallback_chain:
            if fallback == level:
                continue
            fb = get_music_url(song_id, fallback)
            fb_items = fb.get("data", fb)
            if isinstance(fb_items, list):
                for item in fb_items:
                    if item.get("url") and item.get("code") == 200:
                        download_url = item["url"]
                        actual_br = item.get("br", 0)
                        actual_level = item.get("level", fallback) or fallback
                        break
            if download_url:
                break

    if not download_url:
        return {"success": False, "message": f"无法获取 {QUALITY_LEVELS.get(level, {}).get('label', level)} 下载链接"}

    # 4. 构建安全文件名
    safe_artist = "".join(c for c in artist_name if c not in r'\/:*?"<>|') if artist_name else "unknown"
    safe_name = "".join(c for c in song_name if c not in r'\/:*?"<>|') if song_name else "unknown"
    ext = ".mp3" if actual_br < 300000 else ".flac"
    filename = f"{safe_artist} - {safe_name}{ext}"
    filepath = save_dir / filename

    # 5. 流式下载
    try:
        headers = {
            "User-Agent": UA,
            "Referer": "https://music.163.com/",
        }
        resp = requests.get(download_url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        size_mb = downloaded / (1024 * 1024)
        quality_label = QUALITY_LEVELS.get(actual_level, {}).get("label", actual_level)
        bitrate_str = f"{actual_br // 1000}kbps" if actual_br else "未知"

        return {
            "success": True,
            "path": str(filepath),
            "filename": filename,
            "size_mb": round(size_mb, 2),
            "bitrate": bitrate_str,
            "quality": quality_label,
            "message": f"已下载: {filename} ({size_mb:.1f}MB, {bitrate_str}, {quality_label})",
        }
    except requests.exceptions.RequestException as e:
        # 清理失败的下载
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception:
                pass
        return {"success": False, "message": f"下载失败: {e}"}


def like_song(song_id, like=True):
    """喜欢/取消喜欢歌曲"""
    ts = int(time.time() * 1000)
    result = _get("/like", params={"id": str(song_id), "like": str(like).lower(), "timestamp": ts})
    return result


def get_likelist(uid=None):
    """获取用户红心歌曲列表"""
    ts = int(time.time() * 1000)
    params = {"timestamp": ts}
    if uid:
        params["uid"] = str(uid)
    result = _get("/likelist", params=params)
    return result


def get_simi_song(song_id):
    """获取相似歌曲"""
    ts = int(time.time() * 1000)
    result = _get("/simi/song", params={"id": str(song_id), "timestamp": ts})
    return result


# ==================== 评论相关 ====================

def get_comment_music(song_id, limit=20, offset=0):
    """获取歌曲评论"""
    ts = int(time.time() * 1000)
    result = _get("/comment/music", params={
        "id": str(song_id), "limit": limit, "offset": offset, "timestamp": ts
    })
    return result


def get_comment_playlist(playlist_id, limit=20, offset=0):
    """获取歌单评论"""
    ts = int(time.time() * 1000)
    result = _get("/comment/playlist", params={
        "id": str(playlist_id), "limit": limit, "offset": offset, "timestamp": ts
    })
    return result


def get_comment_album(album_id, limit=20, offset=0):
    """获取专辑评论"""
    ts = int(time.time() * 1000)
    result = _get("/comment/album", params={
        "id": str(album_id), "limit": limit, "offset": offset, "timestamp": ts
    })
    return result


# ==================== 搜索相关 ====================

def cloud_search(keyword, limit=10):
    """搜索"""
    ts = int(time.time() * 1000)
    result = _get("/cloudsearch", params={"keywords": keyword, "type": 1, "limit": limit, "timestamp": ts})
    return result


def search_song(keyword, limit=10):
    """搜索歌曲（高层封装）"""
    result = cloud_search(keyword, limit)
    data = result.get("data", result)

    if data.get("code") == 200 and "result" in data and "songs" in data["result"]:
        songs = []
        for song in data["result"]["songs"]:
            artists = [ar.get("name", "") for ar in song.get("ar", [])]
            songs.append({
                "id": song.get("id"),
                "name": song.get("name", ""),
                "artist": ", ".join(a for a in artists if a),
                "album": song.get("al", {}).get("name", ""),
            })
        return {"success": True, "songs": songs}
    return {"success": False, "error": str(data)}


# ==================== 每日推荐 ====================

def get_recommend_songs():
    """获取每日推荐（原始）"""
    ts = int(time.time() * 1000)
    result = _get("/recommend/songs", params={"timestamp": ts})
    return result


def get_daily_recommendations():
    """获取每日推荐（高层封装）"""
    result = get_recommend_songs()
    # 代理返回: {code: 200, data: {dailySongs: [...]}} 或 {data: {code:...}}
    data = result.get("data", result)
    # 如果 data 里有 code==200，取 data['data']
    if isinstance(data, dict) and data.get("code") == 200:
        daily_songs = data.get("data", {}).get("dailySongs", [])
    elif result.get("code") == 200:
        daily_songs = result.get("data", {}).get("dailySongs", [])
    else:
        daily_songs = []

    if daily_songs:
        songs = []
        for song in daily_songs:
            artists = [ar.get("name", "") for ar in song.get("ar", [])]
            songs.append({
                "id": song.get("id"),
                "name": song.get("name", ""),
                "artist": ", ".join(a for a in artists if a),
                "album": song.get("al", {}).get("name", ""),
            })
        return {"success": True, "songs": songs}
    return {"success": False, "error": str(result)}


# ==================== 推荐 / 其他 ====================

def get_personal_fm():
    """获取私人 FM"""
    ts = int(time.time() * 1000)
    result = _get("/personal_fm", params={"timestamp": ts})
    return result


def get_recommended_song_list(num=10):
    """获取推荐歌单"""
    result = _get("/personalized", params={"limit": num})
    return result


def get_toplist():
    """获取排行榜"""
    result = _get("/toplist")
    return result


def get_user_subcount():
    """获取用户收藏计数"""
    ts = int(time.time() * 1000)
    result = _get("/user/subcount", params={"timestamp": ts})
    return result


# ==================== 歌手相关 ====================

def get_artist_detail(artist_id):
    """获取歌手详情"""
    ts = int(time.time() * 1000)
    result = _get("/artists", params={"id": str(artist_id), "timestamp": ts})
    return result


def get_artist_top_songs(artist_id, limit=20):
    """获取歌手热门歌曲"""
    ts = int(time.time() * 1000)
    result = _get("/artist/top/song", params={"id": str(artist_id), "timestamp": ts})
    return result


def get_artist_albums(artist_id, limit=20):
    """获取歌手专辑列表"""
    ts = int(time.time() * 1000)
    result = _get("/artist/album", params={"id": str(artist_id), "limit": limit, "timestamp": ts})
    return result


def get_artist_mvs(artist_id, limit=20):
    """获取歌手 MV"""
    ts = int(time.time() * 1000)
    result = _get("/artist/mv", params={"id": str(artist_id), "limit": limit, "timestamp": ts})
    return result


# ==================== 专辑相关 ====================

def get_album_detail(album_id):
    """获取专辑详情"""
    ts = int(time.time() * 1000)
    result = _get("/album", params={"id": str(album_id), "timestamp": ts})
    return result


def get_album_new():
    """获取新碟上架"""
    result = _get("/album/newest")
    return result


# ==================== MV 相关 ====================

def get_mv_detail(mv_id):
    """获取 MV 详情"""
    ts = int(time.time() * 1000)
    result = _get("/mv/detail", params={"mvid": str(mv_id), "timestamp": ts})
    return result


def get_mv_url(mv_id, quality=1080):
    """获取 MV 播放 URL"""
    ts = int(time.time() * 1000)
    result = _get("/mv/url", params={"id": str(mv_id), "r": quality, "timestamp": ts})
    return result


def get_personalized_mv():
    """获取推荐 MV"""
    result = _get("/personalized/mv")
    return result


# ==================== 手机号登录 ====================

def send_captcha(phone, countrycode=86):
    """发送验证码"""
    ts = int(time.time() * 1000)
    result = _get("/captcha/sent", params={
        "phone": str(phone), "countrycode": countrycode, "timestamp": ts
    }, auth=False)
    return result


def cellphone_login(phone, captcha, countrycode=86):
    """手机号 + 验证码登录"""
    ts = int(time.time() * 1000)
    result = _get("/login/cellphone", params={
        "phone": str(phone), "captcha": str(captcha),
        "countrycode": countrycode, "timestamp": ts
    }, auth=False)
    data = result.get("data", result)
    if data.get("code") == 200:
        cookie_str = data.get("cookie", "")
        if cookie_str:
            save_cookies(parse_cookie_string(cookie_str))
        return {"success": True, "message": "登录成功"}
    return {"success": False, "message": str(data)}


# ==================== 播放控制 ====================

def play_song(song_id, song_name=None, artist=None):
    """唤起客户端播放歌曲"""
    import sys, subprocess

    command = {"type": "song", "id": str(song_id), "cmd": "play"}
    json_str = json.dumps(command, separators=(",", ":"))
    encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    app_url = f"orpheus://{encoded}"

    try:
        if sys.platform == "win32":
            os.startfile(app_url)
        else:
            subprocess.run(["open", app_url])
        label = f"{song_name} - {artist}" if song_name else str(song_id)
        return f"已发送播放指令: {label}"
    except (OSError, FileNotFoundError):
        web_url = f"https://music.163.com/#/song?id={song_id}"
        if sys.platform == "win32":
            os.startfile(web_url)
        else:
            subprocess.run(["open", web_url])
        return f"已在浏览器中播放: {web_url}"


def play_playlist(playlist_id, playlist_name=None):
    """唤起客户端播放歌单"""
    import sys, subprocess

    command = {"type": "playlist", "id": str(playlist_id), "cmd": "play"}
    json_str = json.dumps(command, separators=(",", ":"))
    encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    app_url = f"orpheus://{encoded}"

    try:
        if sys.platform == "win32":
            os.startfile(app_url)
        else:
            subprocess.run(["open", app_url])
        label = playlist_name or str(playlist_id)
        return f"已发送播放指令: {label}"
    except (OSError, FileNotFoundError):
        web_url = f"https://music.163.com/#/playlist?id={playlist_id}"
        if sys.platform == "win32":
            os.startfile(web_url)
        else:
            subprocess.run(["open", web_url])
        return f"已在浏览器中播放: {web_url}"


# ==================== 歌曲可见性检查 ====================

def check_song_visible(song_id):
    """检查歌曲是否可播放"""
    check = check_music(song_id)
    check_data = check.get("data", check)
    if check_data.get("code") != 200:
        return {"playable": False, "reason": "歌曲不可用（版权/下架）"}
    detail = get_song_detail([song_id])
    detail_data = detail.get("data", detail)
    if detail_data.get("code") == 200 and "songs" in detail_data:
        song = detail_data["songs"][0]
        fee = song.get("fee", 0)
        if fee == 4:
            return {"playable": False, "reason": "付费专辑，需单独购买"}
        privilege = song.get("privilege", {})
        if privilege.get("st", 0) < 0:
            return {"playable": False, "reason": "已下架或不可用"}
        return {
            "playable": True, "reason": "",
            "fee": fee, "vip_only": fee == 1,
            "name": song.get("name", ""),
            "artist": ", ".join(ar.get("name", "") for ar in song.get("ar", [])),
        }
    return {"playable": False, "reason": "无法获取歌曲信息"}


def make_web_link(resource_type, resource_id):
    """生成网易云音乐网页链接"""
    return f"https://music.163.com/#/{resource_type}?id={resource_id}"


# ==================== 歌单创建与管理 ====================

def create_playlist(name, description=""):
    """创建歌单"""
    ts = int(time.time() * 1000)
    data = {"name": name, "timestamp": ts}
    if description:
        data["description"] = description
    return _post("/playlist/create", data=data)


def add_songs_to_playlist(playlist_id, song_ids):
    """添加歌曲到歌单"""
    ts = int(time.time() * 1000)
    tracks = ",".join(str(sid) for sid in song_ids)
    return _get("/playlist/tracks", params={
        "op": "add", "pid": str(playlist_id),
        "tracks": tracks, "timestamp": ts,
    })


# ==================== 播放队列管理 ====================

_queue = []


def queue_add(song_id, song_name="", artist=""):
    """添加歌曲到播放队列（内存）"""
    _queue.append({"id": str(song_id), "name": song_name, "artist": artist})
    return len(_queue)


def queue_get():
    """获取当前队列"""
    return list(_queue)


def queue_clear():
    """清空队列"""
    _queue.clear()
    return 0


def queue_play(max_songs=50):
    """播放队列：创建临时歌单 → 加歌 → 播放"""
    if not _queue:
        return {"success": False, "message": "队列为空"}
    songs = _queue[:max_songs]
    names = [f"{s.get('name', '')} - {s.get('artist', '')}" for s in songs]
    playlist_name = f"MCP队列 - {time.strftime('%H:%M:%S')}"
    create_result = create_playlist(playlist_name)
    create_data = create_result.get("data", create_result)
    # /playlist/create 返回 {code: 200, playlist: {id: xxx}} 或 {code: 200, id: xxx}
    create_body = create_data.get("body", create_data)
    if create_data.get("code") != 200 and create_body.get("code") != 200:
        return {"success": False, "message": f"创建临时歌单失败: {create_body}"}
    pid = (create_data.get("playlist", {}).get("id") or
           create_body.get("id") or
           create_data.get("id"))
    if not pid:
        return {"success": False, "message": "无法获取歌单ID"}
    song_ids = [s["id"] for s in songs]
    add_result = add_songs_to_playlist(pid, song_ids)
    add_data = add_result.get("data", add_result)
    # /playlist/tracks 返回 {body: {code: 200}} 或直接 {code: 200}
    add_body = add_data.get("body", add_data)
    if add_body.get("code") != 200:
        return {"success": False, "message": f"添加歌曲失败: {add_body}"}
    play_playlist(pid, playlist_name)
    _queue.clear()
    return {
        "success": True,
        "message": f"已播放 {len(songs)} 首歌",
        "playlist_id": pid,
        "songs": names,
        "web_link": make_web_link("playlist", pid),
    }


# ==================== 偏好分析 ====================

def get_liked_songs_for_analysis(limit=200):
    """获取红心歌曲详细信息用于偏好分析"""
    cookies = load_cookies()
    uid = cookies.get("__uid", "")
    if not uid:
        status = get_current_login_status()
        status_data = status.get("data", status)
        if status_data.get("code") == 200:
            uid = (status_data.get("profile", {}).get("userId") or
                   status_data.get("account", {}).get("id", ""))
    if not uid:
        return {"success": False, "error": "无法获取用户ID，请先登录"}
    result = get_likelist(uid)
    data = result.get("data", result)
    if data.get("code") != 200:
        return {"success": False, "error": "获取红心列表失败"}
    all_ids = data.get("ids", [])
    recent_ids = all_ids[-limit:] if len(all_ids) > limit else all_ids
    recent_ids = list(reversed(recent_ids))
    songs_data = []
    for i in range(0, len(recent_ids), 100):
        batch = recent_ids[i:i+100]
        detail = get_song_detail(batch)
        detail_data = detail.get("data", detail)
        if detail_data.get("code") == 200 and "songs" in detail_data:
            for song in detail_data["songs"]:
                artists = [ar.get("name", "") for ar in song.get("ar", [])]
                songs_data.append({
                    "id": song.get("id"),
                    "name": song.get("name", ""),
                    "artist": ", ".join(artists),
                    "album": song.get("al", {}).get("name", ""),
                    "duration": song.get("dt", 0),
                    "fee": song.get("fee", 0),
                    "publish_time": song.get("publishTime", 0),
                    "origin_cover_type": song.get("originCoverType", 0),
                    "mark": song.get("mark", 0),
                })
    return {
        "success": True,
        "total_liked": len(all_ids),
        "analyzed_count": len(songs_data),
        "songs": songs_data,
    }
