#!/usr/bin/env python3
"""
网易云音乐 MCP 服务器（完整版）
通过本地 Node.js API 代理处理加密，提供全功能 MCP 工具接口
"""
import os
import sys
import time
import subprocess

os.environ["LOGURU_LEVEL"] = "WARNING"
os.environ["CI"] = "true"

from fastmcp import FastMCP

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from cloud_music_mcp.server import start as start_proxy
from cloud_music_mcp.api import (
    # 登录
    check_login_status, login_via_qrcode, clear_cookies,
    send_captcha, cellphone_login,
    # 歌单
    get_user_playlists, get_playlist_detail, get_playlist_all,
    create_playlist, add_songs_to_playlist,
    # 歌曲
    get_song_detail, get_music_url, get_lyric, check_music,
    like_song, get_likelist, get_simi_song,
    check_song_visible, make_web_link,
    # 下载 & VIP
    download_song, get_vip_info, QUALITY_LEVELS,
    # 队列
    queue_add, queue_get, queue_clear, queue_play,
    # 偏好分析
    get_liked_songs_for_analysis,
    # 评论
    get_comment_music, get_comment_playlist, get_comment_album,
    # 搜索
    search_song,
    # 每日推荐
    get_daily_recommendations,
    # 推荐 / FM
    get_personal_fm, get_recommended_song_list, get_toplist,
    # 用户
    get_user_subcount,
    # 歌手
    get_artist_detail, get_artist_top_songs, get_artist_albums, get_artist_mvs,
    # 专辑
    get_album_detail, get_album_new,
    # MV
    get_mv_detail, get_mv_url, get_personalized_mv,
)

_API_READY = False
try:
    start_proxy()
    _API_READY = True
except Exception as e:
    print(f"[cloud-music-mcp] 警告: API 代理启动失败: {e}", file=sys.stderr)

mcp = FastMCP("Cloud-Music-MCP")


def _guard():
    """检查代理可用性"""
    if not _API_READY:
        return "❌ API 代理未就绪"
    return None


def _parse_duration(dt_ms):
    """毫秒转 分:秒 字符串"""
    if not dt_ms:
        return ""
    total_sec = dt_ms // 1000
    mins, secs = divmod(total_sec, 60)
    return f"{mins}:{secs:02d}"


# ==================== 登录 (3个) ====================

@mcp.tool()
def cloud_music_status():
    """检查网易云音乐登录状态"""
    if e := _guard(): return e
    s = check_login_status()
    return f"✅ 已登录: {s['nickname']}" if s["logged_in"] else "❌ 未登录"


@mcp.tool()
def cloud_music_login():
    """扫码登录 - 弹出二维码图片，用网易云音乐 App 扫码"""
    if e := _guard(): return e
    r = login_via_qrcode()
    return f"✅ {r['message']}" if r["success"] else f"❌ {r.get('message')}"


@mcp.tool()
def cloud_music_phone_login(phone: str, captcha: str, countrycode: int = 86):
    """
    手机号+验证码登录

    Args:
        phone: 手机号
        captcha: 验证码（先用 cloud_music_send_captcha 获取）
        countrycode: 国家代码，默认86
    """
    if e := _guard(): return e
    r = cellphone_login(phone, captcha, countrycode)
    return f"✅ {r['message']}" if r["success"] else f"❌ {r.get('message')}"


@mcp.tool()
def cloud_music_send_captcha(phone: str, countrycode: int = 86):
    """
    发送登录验证码

    Args:
        phone: 手机号
        countrycode: 国家代码，默认86
    """
    if e := _guard(): return e
    r = send_captcha(phone, countrycode)
    data = r.get("data", r)
    return f"✅ 验证码已发送" if data.get("code") == 200 else f"❌ {data.get('message', '发送失败')}"


@mcp.tool()
def cloud_music_logout():
    """退出登录"""
    clear_cookies()
    return "✅ 已退出登录"


# ==================== 歌单 (3个) ====================

@mcp.tool()
def cloud_music_my_playlists():
    """获取我的歌单（含创建和收藏）"""
    if e := _guard(): return e
    r = get_user_playlists()
    if not r["success"]:
        return f"❌ {r.get('error')}"
    pls = r["playlists"]
    if not pls:
        return "📚 暂无歌单"
    text = f"📚 我的歌单 ({len(pls)}个):\n\n"
    liked = [p for p in pls if "喜欢" in p.get('name', '')]
    mine = [p for p in pls if p.get('is_mine') and "喜欢" not in p.get('name', '')]
    others = [p for p in pls if not p.get('is_mine') and "喜欢" not in p.get('name', '')]
    for label, items in [("❤️ 喜欢", liked), ("👤 创建", mine), ("⭐ 收藏", others)]:
        if items:
            text += f"{label}\n"
            for pl in items:
                text += f"   • {pl['name']} ({pl['count']}首) ID: {pl['id']}\n"
            text += "\n"
    text += "💡 cloud_music_playlist_detail(id) 查看详情"
    return text


@mcp.tool()
def cloud_music_playlist_detail(playlist_id: str):
    """
    获取歌单详情（含歌曲列表）

    Args:
        playlist_id: 歌单ID
    """
    if e := _guard(): return e
    r = get_playlist_detail(playlist_id)
    if not r["success"]:
        return f"❌ {r.get('error')}"
    info = r["info"]
    songs = r["songs"]
    text = f"📋 {info['name']}\n👤 {info.get('creator','?')} | 🎵 {len(songs)}首\n\n"
    for i, s in enumerate(songs[:20], 1):
        text += f"{i:2}. {s['name']} - {s['artist']} (ID:{s['id']})\n"
    if len(songs) > 20:
        text += f"\n... 还有 {len(songs) - 20} 首\n"
        text += "💡 cloud_music_play(type='playlist', id='...') 播放全部"
    return text


@mcp.tool()
def cloud_music_playlist_all(playlist_id: str, limit: int = 500):
    """
    获取歌单所有歌曲

    Args:
        playlist_id: 歌单ID
        limit: 最多返回数量，默认500
    """
    if e := _guard(): return e
    r = get_playlist_all(playlist_id, limit=limit)
    if not r["success"]:
        return f"❌ {r.get('error')}"
    text = f"🎵 共 {len(r['songs'])} 首\n\n"
    for i, s in enumerate(r['songs'][:30], 1):
        text += f"{i:2}. {s['name']} - {s['artist']} (ID:{s['id']})\n"
    if len(r['songs']) > 30:
        text += f"\n... 还有 {len(r['songs'])-30} 首"
    return text


# ==================== 歌曲 (6个) ====================

@mcp.tool()
def cloud_music_song_detail(song_id: str):
    """
    获取歌曲详情

    Args:
        song_id: 歌曲ID
    """
    if e := _guard(): return e
    r = get_song_detail(song_id)
    data = r.get("data", r)
    if data.get("code") == 200 and "songs" in data:
        song = data["songs"][0]
        artists = ", ".join(ar.get("name", "") for ar in song.get("ar", []))
        album = song.get("al", {}).get("name", "")
        duration = _parse_duration(song.get("dt", 0))
        return f"🎵 {song.get('name')}\n歌手: {artists}\n专辑: {album}\n时长: {duration}\nID: {song_id}"
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_lyric(song_id: str):
    """
    获取歌词

    Args:
        song_id: 歌曲ID
    """
    if e := _guard(): return e
    r = get_lyric(song_id)
    data = r.get("data", r)
    if data.get("code") == 200:
        lrc = data.get("lrc", {}).get("lyric", "无歌词")
        # 去掉时间标签显示纯文本
        import re
        clean = re.sub(r'\[.*?\]', '', lrc).strip()
        tlyric = data.get("tlyric", {}).get("lyric", "")
        if tlyric:
            clean += "\n\n--- 翻译 ---\n" + re.sub(r'\[.*?\]', '', tlyric).strip()
        return clean[:3000] if clean else "无歌词"
    return "❌ 获取歌词失败"


@mcp.tool()
def cloud_music_song_url(song_id: str, level: str = "lossless"):
    """
    获取歌曲播放 URL

    Args:
        song_id: 歌曲ID
        level: 音质等级 — standard/higher/exhigh/lossless/hires/jyeffect/sky/dolby/jymaster
    """
    if e := _guard(): return e
    r = get_music_url(song_id, level)
    items = r.get("data", r)  # data 是数组 [{id, url, br, level, ...}]
    if isinstance(items, list):
        for item in items:
            url = item.get("url", "")
            br = item.get("br", 0) // 1000
            lv = item.get("level", level)
            ql = QUALITY_LEVELS.get(lv, {}).get("label", lv)
            if url and item.get("code") == 200:
                return f"🔗 {ql} {br}kbps\n{url}"
        return "⚠️ 无可用播放链接（版权受限/音质不可用）"
    return "❌ 获取 URL 失败"


@mcp.tool()
def cloud_music_like(song_id: str, like: bool = True):
    """
    喜欢/取消喜欢歌曲

    Args:
        song_id: 歌曲ID
        like: True=喜欢，False=取消喜欢
    """
    if e := _guard(): return e
    r = like_song(song_id, like)
    data = r.get("data", r)
    if data.get("code") == 200:
        return "❤️ 已标记喜欢" if like else "💔 已取消喜欢"
    return "❌ 操作失败"


@mcp.tool()
def cloud_music_likelist():
    """获取我的红心歌曲列表"""
    if e := _guard(): return e
    r = get_likelist()
    data = r.get("data", r)
    if data.get("code") == 200:
        ids = data.get("ids", [])
        return f"❤️ 共 {len(ids)} 首红心歌曲"
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_simi_song(song_id: str):
    """
    获取相似歌曲推荐

    Args:
        song_id: 歌曲ID
    """
    if e := _guard(): return e
    r = get_simi_song(song_id)
    data = r.get("data", r)
    if data.get("code") == 200 and "songs" in data:
        text = "🎵 相似歌曲:\n\n"
        for i, s in enumerate(data["songs"][:10], 1):
            artists = ", ".join(ar.get("name", "") for ar in s.get("artists", []))
            text += f"{i}. {s.get('name')} - {artists} (ID:{s.get('id')})\n"
        return text
    return "❌ 获取失败"


# ==================== 搜索 (1个) ====================

@mcp.tool()
def cloud_music_search(keyword: str, limit: int = 10):
    """
    搜索歌曲

    Args:
        keyword: 搜索关键词（歌名/歌手/专辑）
        limit: 返回数量，默认10
    """
    if e := _guard(): return e
    r = search_song(keyword, limit=limit)
    if not r["success"]:
        return f"❌ {r.get('error')}"
    if not r["songs"]:
        return f"🔍 没有找到「{keyword}」"
    text = f"🔍 「{keyword}」({len(r['songs'])}首):\n\n"
    for i, s in enumerate(r["songs"], 1):
        text += f"{i}. {s['name']} - {s['artist']} (ID:{s['id']})\n"
    text += "\n💡 cloud_music_play(id='歌曲ID') 播放"
    return text


# ==================== 每日推荐 / FM (3个) ====================

@mcp.tool()
def cloud_music_daily_recommend():
    """获取每日推荐歌曲（需登录）"""
    if e := _guard(): return e
    r = get_daily_recommendations()
    if not r["success"]:
        return f"❌ {r.get('error')}"
    songs = r["songs"]
    if not songs:
        return "📅 今日暂无推荐"
    text = f"📅 今日推荐 ({len(songs)}首):\n\n"
    for i, s in enumerate(songs[:15], 1):
        text += f"{i:2}. {s['name']} - {s['artist']} (ID:{s['id']})\n"
    if len(songs) > 15:
        text += f"\n... 还有 {len(songs)-15} 首"
    text += "\n💡 cloud_music_play(id='歌曲ID') 播放"
    return text


@mcp.tool()
def cloud_music_personal_fm():
    """获取私人 FM（需登录）"""
    if e := _guard(): return e
    r = get_personal_fm()
    data = r.get("data", r)
    if data.get("code") == 200 and "data" in data:
        songs = data["data"]
        text = "📻 私人 FM:\n\n"
        for i, s in enumerate(songs[:10], 1):
            artists = ", ".join(ar.get("name", "") for ar in s.get("artists", []))
            text += f"{i}. {s.get('name')} - {artists} (ID:{s.get('id')})\n"
        return text
    return "❌ 获取私人 FM 失败"


@mcp.tool()
def cloud_music_recommend_playlists(count: int = 10):
    """
    获取推荐歌单

    Args:
        count: 数量，默认10
    """
    if e := _guard(): return e
    r = get_recommended_song_list(count)
    data = r.get("data", r)
    if data.get("code") == 200 and "result" in data:
        text = f"📋 推荐歌单:\n\n"
        for i, pl in enumerate(data["result"][:count], 1):
            text += f"{i:2}. {pl.get('name')} (ID:{pl.get('id')})\n"
        return text
    return "❌ 获取失败"


# ==================== 评论 (3个) ====================

@mcp.tool()
def cloud_music_comment_song(song_id: str, limit: int = 10):
    """
    获取歌曲热门评论

    Args:
        song_id: 歌曲ID
        limit: 数量，默认10
    """
    if e := _guard(): return e
    r = get_comment_music(song_id, limit=limit)
    data = r.get("data", r)
    if data.get("code") == 200:
        comments = data.get("hotComments", data.get("comments", []))
        if not comments:
            return "💬 暂无热门评论"
        text = f"💬 热门评论:\n\n"
        for i, c in enumerate(comments[:limit], 1):
            user = c.get("user", {}).get("nickname", "用户")
            content = c.get("content", "")
            liked = c.get("likedCount", 0)
            text += f"{i}. {user} ({liked}赞):\n   {content}\n\n"
        return text[:3000]
    return "❌ 获取评论失败"


@mcp.tool()
def cloud_music_comment_playlist(playlist_id: str, limit: int = 10):
    """
    获取歌单热门评论

    Args:
        playlist_id: 歌单ID
        limit: 数量，默认10
    """
    if e := _guard(): return e
    r = get_comment_playlist(playlist_id, limit=limit)
    data = r.get("data", r)
    if data.get("code") == 200:
        comments = data.get("hotComments", data.get("comments", []))
        if not comments:
            return "💬 暂无热门评论"
        text = f"💬 热门评论:\n\n"
        for i, c in enumerate(comments[:limit], 1):
            user = c.get("user", {}).get("nickname", "用户")
            content = c.get("content", "")
            liked = c.get("likedCount", 0)
            text += f"{i}. {user} ({liked}赞):\n   {content}\n\n"
        return text[:3000]
    return "❌ 获取评论失败"


@mcp.tool()
def cloud_music_comment_album(album_id: str, limit: int = 10):
    """
    获取专辑热门评论

    Args:
        album_id: 专辑ID
        limit: 数量，默认10
    """
    if e := _guard(): return e
    r = get_comment_album(album_id, limit=limit)
    data = r.get("data", r)
    if data.get("code") == 200:
        comments = data.get("hotComments", data.get("comments", []))
        if not comments:
            return "💬 暂无热门评论"
        text = f"💬 热门评论:\n\n"
        for i, c in enumerate(comments[:limit], 1):
            user = c.get("user", {}).get("nickname", "用户")
            content = c.get("content", "")
            liked = c.get("likedCount", 0)
            text += f"{i}. {user} ({liked}赞):\n   {content}\n\n"
        return text[:3000]
    return "❌ 获取评论失败"


# ==================== 歌手 (4个) ====================

@mcp.tool()
def cloud_music_artist_detail(artist_id: str):
    """
    获取歌手详情

    Args:
        artist_id: 歌手ID
    """
    if e := _guard(): return e
    r = get_artist_detail(artist_id)
    data = r.get("data", r)
    if data.get("code") == 200:
        artist = data.get("artist", {})
        return (
            f"🎤 {artist.get('name')}\n"
            f"别名: {', '.join(artist.get('alias', [])) or '无'}\n"
            f"专辑数: {artist.get('albumSize', 0)}\n"
            f"MV数: {artist.get('mvSize', 0)}\n"
            f"简介: {artist.get('briefDesc', '暂无')[:200]}"
        )
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_artist_top_songs(artist_id: str, limit: int = 20):
    """
    获取歌手热门歌曲

    Args:
        artist_id: 歌手ID
        limit: 数量，默认20
    """
    if e := _guard(): return e
    r = get_artist_top_songs(artist_id)
    data = r.get("data", r)
    if data.get("code") == 200:
        songs = data.get("songs", data.get("hotSongs", []))
        text = f"🎤 热门歌曲:\n\n"
        for i, s in enumerate(songs[:limit], 1):
            artists = ", ".join(ar.get("name", "") for ar in s.get("ar", []))
            text += f"{i:2}. {s.get('name')} - {artists} (ID:{s.get('id')})\n"
        return text
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_artist_albums(artist_id: str, limit: int = 20):
    """
    获取歌手专辑列表

    Args:
        artist_id: 歌手ID
        limit: 数量，默认20
    """
    if e := _guard(): return e
    r = get_artist_albums(artist_id, limit=limit)
    data = r.get("data", r)
    if data.get("code") == 200:
        albums = data.get("hotAlbums", [])
        text = f"💿 专辑:\n\n"
        for i, al in enumerate(albums[:limit], 1):
            text += f"{i:2}. {al.get('name')} ({al.get('publishTime','?')[:4]}) ID:{al.get('id')}\n"
        return text if text.strip().endswith('\n') else text
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_artist_mvs(artist_id: str, limit: int = 10):
    """
    获取歌手 MV

    Args:
        artist_id: 歌手ID
        limit: 数量，默认10
    """
    if e := _guard(): return e
    r = get_artist_mvs(artist_id, limit=limit)
    data = r.get("data", r)
    if data.get("code") == 200:
        mvs = data.get("mvs", [])
        text = f"📽️ MV:\n\n"
        for i, mv in enumerate(mvs[:limit], 1):
            text += f"{i:2}. {mv.get('name')} (ID:{mv.get('id')})\n"
        return text or "暂无 MV"
    return "❌ 获取失败"


# ==================== 专辑 (2个) ====================

@mcp.tool()
def cloud_music_album_detail(album_id: str):
    """
    获取专辑详情

    Args:
        album_id: 专辑ID
    """
    if e := _guard(): return e
    r = get_album_detail(album_id)
    data = r.get("data", r)
    if data.get("code") == 200:
        album = data.get("album", {})
        songs = album.get("songs", [])
        artists = ", ".join(ar.get("name", "") for ar in album.get("artists", []))
        pub = album.get("publishTime", 0)
        pub_str = str(pub)[:4] if pub else "未知"
        text = f"💿 {album.get('name')}\n👤 {artists} | {pub_str} | {len(songs)}首\n\n"
        for i, s in enumerate(songs[:20], 1):
            ars = ", ".join(ar.get("name", "") for ar in s.get("ar", []))
            text += f"{i:2}. {s.get('name')} - {ars} (ID:{s.get('id')})\n"
        if len(songs) > 20:
            text += f"\n... 还有 {len(songs)-20} 首"
        return text
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_album_new():
    """获取最新专辑"""
    if e := _guard(): return e
    r = get_album_new()
    data = r.get("data", r)
    if data.get("code") == 200:
        albums = data.get("albums", [])
        text = "🆕 新碟上架:\n\n"
        for i, al in enumerate(albums[:15], 1):
            ars = ", ".join(ar.get("name", "") for ar in al.get("artists", []))
            text += f"{i:2}. {al.get('name')} - {ars} (ID:{al.get('id')})\n"
        return text
    return "❌ 获取失败"


# ==================== MV (3个) ====================

@mcp.tool()
def cloud_music_mv_detail(mv_id: str):
    """
    获取 MV 详情

    Args:
        mv_id: MV ID
    """
    if e := _guard(): return e
    r = get_mv_detail(mv_id)
    data = r.get("data", r)
    if data.get("code") == 200:
        mv = data.get("data", {})
        artists = ", ".join(ar.get("name", "") for ar in mv.get("artists", []))
        return (
            f"📽️ {mv.get('name')}\n"
            f"👤 {artists}\n"
            f"播放: {mv.get('playCount', 0)}\n"
            f"时长: {_parse_duration(mv.get('duration', 0)*1000) or '未知'}\n"
            f"ID: {mv_id}"
        )
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_mv_url(mv_id: str, quality: int = 1080):
    """
    获取 MV 播放地址

    Args:
        mv_id: MV ID
        quality: 分辨率 - 240/480/720/1080
    """
    if e := _guard(): return e
    r = get_mv_url(mv_id, quality)
    data = r.get("data", r)
    if data.get("code") == 200:
        url = data.get("data", {}).get("url", "")
        return f"🔗 {url}" if url else "⚠️ 无可用播放链接"
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_mv_recommend():
    """获取推荐 MV"""
    if e := _guard(): return e
    r = get_personalized_mv()
    data = r.get("data", r)
    if data.get("code") == 200 and "result" in data:
        mvs = data["result"]
        text = f"📽️ 推荐 MV:\n\n"
        for i, mv in enumerate(mvs[:10], 1):
            artists = ", ".join(ar.get("name", "") for ar in mv.get("artists", []))
            text += f"{i:2}. {mv.get('name')} - {artists} (ID:{mv.get('id')})\n"
        return text
    return "❌ 获取失败"


# ==================== 用户 / 排行榜 (2个) ====================

@mcp.tool()
def cloud_music_user_subcount():
    """获取我的收藏计数"""
    if e := _guard(): return e
    r = get_user_subcount()
    data = r.get("data", r)
    if data.get("code") == 200:
        sc = data.get("data", data)
        lines = [
            f"📊 我的收藏",
            f"歌单: {sc.get('createdPlaylistCount', 0)} 创建 / {sc.get('subPlaylistCount', 0)} 收藏",
            f"歌曲: {sc.get('songCount', 0)} 首",
            f"专辑: {sc.get('albumCount', 0)} 张",
            f"歌手: {sc.get('artistCount', 0)} 位",
            f"MV: {sc.get('mvCount', 0)} 个",
            f"电台: {sc.get('djRadioCount', 0)} 个",
        ]
        return "\n".join(lines)
    return "❌ 获取失败"


@mcp.tool()
def cloud_music_toplist():
    """获取排行榜"""
    if e := _guard(): return e
    r = get_toplist()
    data = r.get("data", r)
    if data.get("code") == 200:
        lists = data.get("list", [])
        text = "🏆 排行榜:\n\n"
        for i, tl in enumerate(lists[:15], 1):
            text += f"{i:2}. {tl.get('name')} (ID:{tl.get('id')})\n"
        return text
    return "❌ 获取失败"


# ==================== 播放 (1个) ====================

@mcp.tool()
def cloud_music_play(id: str, type: str = "song"):
    """
    播放歌曲/歌单/MV/专辑（自动检查歌曲可见性）

    Args:
        id: ID
        type: 'song'(歌曲) / 'playlist'(歌单) / 'mv'(MV) / 'album'(专辑)
    """
    web_link = make_web_link(type, id)

    # 歌曲：先检查可见性
    if type == "song":
        vis = check_song_visible(id)
        if not vis.get("playable"):
            return f"⚠️ 无法播放\n🎵 {vis.get('name', id)}\n❌ {vis['reason']}\n🔗 {web_link}"
        info = f"🎵 {vis.get('name', id)} - {vis.get('artist', '')}"
        if vis.get("vip_only"):
            info += " [VIP]"
    else:
        info = f"{type} ID: {id}"

    # 通过 orpheus 唤起
    import sys as _sys
    try:
        from cloud_music_mcp.api import play_song, play_playlist
        if type in ("song", "mv"):
            play_song(id)
        else:
            play_playlist(id)
        return f"▶️ {info}\n🔗 {web_link}"
    except Exception:
        try:
            if _sys.platform == "win32":
                subprocess.run(["powershell", "-Command", f'Start-Process "{web_link}"'], check=True)
            else:
                subprocess.run(["open", web_link], check=True)
            return f"⚠️ 已通过浏览器打开\n🔗 {web_link}"
        except Exception as ex:
            return f"❌ 播放失败: {ex}\n🔗 {web_link}"


# ==================== 播放队列 (4个) ====================

@mcp.tool()
def cloud_music_queue_add(id: str, name: str = "", artist: str = ""):
    """
    添加歌曲到播放队列（先不播放）

    Args:
        id: 歌曲ID
        name: 歌曲名（可选）
        artist: 歌手名（可选）
    """
    if e := _guard(): return e
    # 内容安全检查
    if name:
        from cloud_music_mcp.api import check_content_safe
        cs = check_content_safe(name)
        if not cs["safe"]:
            return f"⚠️ {cs['reason']}"
    count = queue_add(id, name, artist)
    info = f"{name} - {artist}" if name else id
    return f"📋 已加入队列 (#{count}): {info}\n💡 使用 cloud_music_queue_show 查看队列\n▶️ 使用 cloud_music_queue_play 播放全部"


@mcp.tool()
def cloud_music_queue_show():
    """查看当前播放队列"""
    if e := _guard(): return e
    q = queue_get()
    if not q:
        return "📋 队列为空\n💡 使用 cloud_music_queue_add 添加歌曲"
    lines = [f"📋 播放队列 ({len(q)} 首):"]
    for i, s in enumerate(q, 1):
        label = f"{s.get('name', '')} - {s.get('artist', '')}" if s.get('name') else s['id']
        lines.append(f"  {i:2}. {label}  🔗 {make_web_link('song', s['id'])}")
    return "\n".join(lines)


@mcp.tool()
def cloud_music_queue_clear():
    """清空播放队列"""
    if e := _guard(): return e
    queue_clear()
    return "🗑️ 队列已清空"


@mcp.tool()
def cloud_music_queue_play():
    """播放队列中的所有歌曲（通过创建临时歌单）"""
    if e := _guard(): return e
    r = queue_play()
    if r["success"]:
        lines = [f"▶️ {r['message']}"]
        for i, name in enumerate(r.get("songs", []), 1):
            lines.append(f"  {i:2}. {name}")
        lines.append(f"🔗 {r.get('web_link', '')}")
        return "\n".join(lines)
    return f"❌ {r['message']}"


# ==================== 歌单管理 (2个) ====================

@mcp.tool()
def cloud_music_create_playlist(name: str, description: str = "", song_ids: str = ""):
    """
    创建歌单，可选添加歌曲

    Args:
        name: 歌单名称
        description: 歌单描述（可选）
        song_ids: 歌曲ID列表，逗号分隔（可选，如 "123,456,789"）
    """
    if e := _guard(): return e
    r = create_playlist(name, description)
    data = r.get("data", r)
    if data.get("code") == 200:
        pid = (data.get("playlist", {}).get("id") or data.get("id"))
        if not pid:
            return f"❌ 创建歌单失败: {data}"
        lines = [f"✅ 歌单已创建: {name}", f"🆔 ID: {pid}"]
        # 添加歌曲
        if song_ids:
            ids = [sid.strip() for sid in song_ids.split(",") if sid.strip()]
            if ids:
                add_r = add_songs_to_playlist(pid, ids)
                add_data = add_r.get("data", add_r)
                if add_data.get("code") == 200:
                    lines.append(f"🎵 已添加 {len(ids)} 首歌曲")
                else:
                    lines.append(f"⚠️ 歌单已创建，但添加歌曲失败: {add_data}")
        lines.append(f"🔗 {make_web_link('playlist', pid)}")
        return "\n".join(lines)
    return f"❌ 创建歌单失败: {data}"


# ==================== 偏好分析 (1个) ====================

@mcp.tool()
def cloud_music_preference_analysis():
    """
    分析红心歌曲偏好画像（多维度：曲风、艺人、语言、情绪等）

    基于最近200首红心歌曲进行内容+风格分析，生成用户音乐偏好画像。
    """
    if e := _guard(): return e
    from collections import Counter

    r = get_liked_songs_for_analysis(limit=200)
    if not r.get("success"):
        return f"❌ {r.get('error', '分析失败')}"

    songs = r.get("songs", [])
    if not songs:
        return "⚠️ 未找到红心歌曲数据"

    # 统计维度
    artist_counter = Counter()
    album_counter = Counter()
    total_duration = 0
    fee_counter = Counter()
    cover_type_counter = Counter()

    for s in songs:
        artists = s.get("artist", "").split(", ")
        for ar in artists[:2]:
            artist_counter[ar] += 1
        album_counter[s.get("album", "")] += 1
        total_duration += s.get("duration", 0)
        fee_counter[s.get("fee", 0)] += 1
        cover_type_counter[s.get("origin_cover_type", 0)] += 1

    # 语言分布
    chinese_count = 0
    japanese_count = 0
    english_count = 0
    for s in songs:
        name = s.get("name", "") + s.get("artist", "")
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in name)
        has_kana = any('\u3040' <= c <= '\u30ff' for c in name)
        if has_kana:
            japanese_count += 1
        elif has_cjk:
            chinese_count += 1
        else:
            english_count += 1

    # 平均时长
    avg_duration_ms = total_duration // max(len(songs), 1)
    avg_mins, avg_secs = divmod(avg_duration_ms // 1000, 60)

    # 付费类型分布
    fee_labels = {0: "免费", 1: "VIP专享", 4: "付费专辑", 8: "付费单曲"}

    top_artists = artist_counter.most_common(8)
    top_albums = album_counter.most_common(3)

    lines = [
        f"🎧 音乐偏好画像 (基于最近 {r['analyzed_count']} 首 | 总计 {r['total_liked']} 首红心)",
        "",
    ]

    lines.append(f"🌐 语言偏好:")
    total = max(chinese_count + japanese_count + english_count, 1)
    lines.append(f"  华语: {chinese_count}首 ({chinese_count*100//total}%)")
    lines.append(f"  日语: {japanese_count}首 ({japanese_count*100//total}%)")
    lines.append(f"  英语/其他: {english_count}首 ({english_count*100//total}%)")
    lines.append("")

    if top_artists:
        lines.append("🎤 高频艺人:")
        for ar, count in top_artists:
            lines.append(f"  {ar}: {count}首")
        lines.append("")

    if top_albums and top_albums[0][0]:
        lines.append("💿 高重复专辑:")
        for album, count in top_albums:
            if count >= 2:
                lines.append(f"  {album}: {count}首")
        lines.append("")

    lines.append(f"⏱️ 平均时长: {avg_mins}分{avg_secs:02d}秒")

    # 付费分析
    if len(fee_counter) > 1:
        parts = [f"{fee_labels.get(k, str(k))}: {v}首" for k, v in fee_counter.most_common()]
        lines.append(f"💎 付费类型: {', '.join(parts)}")

    lines.append("")
    lines.append("💡 想基于画像智能搜索？试试「根据我的偏好找歌单」或「推荐纯音乐」")
    return "\n".join(lines)


# ==================== 下载 (1个) ====================

@mcp.tool()
def cloud_music_download(song_id: str, level: str = "lossless", save_dir: str = ""):
    """
    下载歌曲到本地

    Args:
        song_id: 歌曲ID
        level: 音质等级 — standard/higher/exhigh/lossless/hires/jyeffect/sky/dolby/jymaster
        save_dir: 保存目录（默认 ~/Downloads/CloudMusic/）
    """
    if e := _guard(): return e
    r = download_song(song_id, level, save_dir or None)
    if r["success"]:
        return f"✅ {r['message']}\n📁 {r['path']}"
    return f"❌ {r['message']}"


# ==================== VIP 信息 (1个) ====================

@mcp.tool()
def cloud_music_vip_info():
    """获取黑胶VIP信息（等级、会员类型、到期时间等）"""
    if e := _guard(): return e
    r = get_vip_info()
    if r.get("code") == 200:
        info = r.get("data", {})
        from datetime import datetime

        # 用户等级
        level_resp = r.get("_level", {})
        user_level = level_resp.get("data", {}).get("level", "?") if level_resp.get("code") == 200 else "?"

        lines = [f"⭐ 用户等级: Lv.{user_level}"]

        # 核心黑胶SVIP (redplus, vipCode=300)
        redplus = info.get("redplus", {})
        if redplus and redplus.get("expireTime", 0) > int(time.time() * 1000):
            dt = datetime.fromtimestamp(redplus["expireTime"] // 1000)
            lines.append(f"💎 黑胶SVIP Lv.{redplus.get('vipLevel', '?')} | 到期: {dt.strftime('%Y-%m-%d')}")
        else:
            lines.append("💎 黑胶SVIP: 未开通")

        # 音乐包 (musicPackage, vipCode=220)
        music_pkg = info.get("musicPackage", {})
        if music_pkg and music_pkg.get("expireTime", 0) > int(time.time() * 1000):
            dt = datetime.fromtimestamp(music_pkg["expireTime"] // 1000)
            lines.append(f"🎵 音乐包 Lv.{music_pkg.get('vipLevel', '?')} | 到期: {dt.strftime('%Y-%m-%d')}")

        # 黑胶VIP等级
        lines.append(f"🏅 红V等级: Lv.{info.get('redVipLevel', '?')} | 年费: {'是' if info.get('redVipAnnualCount', 0) > 0 else '否'}")

        # 家庭VIP
        family = info.get("familyVip", {})
        if family and family.get("expireTime", 0) > int(time.time() * 1000):
            dt = datetime.fromtimestamp(family["expireTime"] // 1000)
            lines.append(f"👨‍👩‍👧 家庭VIP | 到期: {dt.strftime('%Y-%m-%d')}")

        lines.append("")
        lines.append("📌 下载额度由服务器自动管理，SVIP可下载300-500首/月")
        lines.append("   高级音质 (jyeffect/sky/dolby/jymaster) 需SVIP")
        return "\n".join(lines)
    return f"❌ 获取VIP信息失败: {r}"


def run_mcp():
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    run_mcp()
