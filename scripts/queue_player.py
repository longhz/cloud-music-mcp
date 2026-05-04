#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连续播放器 — 播一首 → 等时长 → 自动切下一首 → 播完退出
不创建任何临时歌单，无残留。

用法:
  python scripts/queue_player.py 2651535504 186016 576177
  python scripts/queue_player.py --random 5
  python scripts/queue_player.py --daily 10
  python scripts/queue_player.py --playlist 482655706
"""

import sys
import os
import time
import signal
import random
import subprocess
import locale

# 修复 Windows 中文终端编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src not in sys.path:
    sys.path.insert(0, _src)
os.environ["LOGURU_LEVEL"] = "WARNING"

from cloud_music_mcp.api import (
    get_song_detail, play_song, check_song_visible, make_web_link,
    get_playlist_detail, get_daily_recommendations, get_likelist,
    get_current_login_status, load_cookies,
)

_running = True


def _on_interrupt(sig, frame):
    global _running
    print("\n\n[STOP] 用户中断")
    _running = False


signal.signal(signal.SIGINT, _on_interrupt)


def is_client_running():
    """检测网易云客户端是否在运行"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq cloudmusic.exe"],
                capture_output=True, timeout=5,
            )
            return b"cloudmusic.exe" in result.stdout
        else:
            result = subprocess.run(
                ["pgrep", "-x", "cloudmusic"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
    except Exception:
        return True  # 无法检测时假定在运行


def _get_song_info(song_id):
    """获取歌曲名、歌手、时长（毫秒）"""
    try:
        detail = get_song_detail([song_id])
        data = detail.get("data", detail)
        if data.get("code") == 200 and "songs" in data:
            s = data["songs"][0]
            artists = [ar.get("name", "") for ar in s.get("ar", [])]
            return {
                "id": song_id,
                "name": s.get("name", "unknown"),
                "artist": ", ".join(artists),
                "duration_ms": s.get("dt", 240000),
            }
    except Exception:
        pass
    return {"id": song_id, "name": str(song_id), "artist": "unknown", "duration_ms": 240000}


def _fmt_time(ms):
    total = ms // 1000
    return f"{total // 60}:{total % 60:02d}"


def _play_one(song, index, total):
    """播放一首，等待时长。返回 True=成功, False=跳过/失败, None=客户端已关闭"""
    global _running
    if not _running:
        return False

    # 检视可见性
    vis = check_song_visible(song["id"])
    if not vis.get("playable"):
        print(f"  [SKIP {index}/{total}] {song['name']} - {song['artist']} | {vis['reason']}")
        return False

    duration_str = _fmt_time(song["duration_ms"])
    print(f"\n>> [{index}/{total}] {song['name']} - {song['artist']}")
    print(f"   [{duration_str}]  {make_web_link('song', song['id'])}")
    sys.stdout.flush()

    # 播放
    try:
        play_song(song["id"])
    except Exception as e:
        print(f"   [FAIL] 播放失败: {e}")
        return False

    # 给客户端启动时间
    time.sleep(2.0)
    wait_sec = max(0, song["duration_ms"] / 1000 - 2.0)

    # 等待播放完成，每 3 秒检测一次客户端存活
    elapsed = 0.0
    check_interval = 3.0
    while elapsed < wait_sec and _running:
        sleep_chunk = min(check_interval, wait_sec - elapsed)
        time.sleep(sleep_chunk)
        elapsed += sleep_chunk

        # 检测客户端是否还活着
        if not is_client_running():
            print(f"\n   [QUIT] 网易云客户端已关闭，停止播放")
            _running = False
            return None

        # 进度显示
        remaining = max(0, wait_sec - elapsed)
        mins, secs = divmod(int(remaining), 60)
        print(f"   [{mins}:{secs:02d}]", end="\r")
        sys.stdout.flush()

    if _running:
        print(f"   [DONE]" + " " * 10)
    return True


def play_sequence(song_ids):
    """按序播放歌曲列表"""
    global _running
    if not song_ids:
        print("[ERR] 没有可播放的歌曲")
        return

    print(f"\n{'=' * 50}")
    print(f"Continuous Player — {len(song_ids)} songs")
    print(f"Press Ctrl+C to stop anytime")
    print(f"{'=' * 50}\n")

    # 检查客户端
    if not is_client_running():
        print("[WARN] 网易云客户端未运行，请先启动")
        return

    songs = []
    for sid in song_ids:
        songs.append(_get_song_info(sid))
        if not _running:
            return

    total_duration = sum(s["duration_ms"] for s in songs)
    print(f"Total: {_fmt_time(total_duration)} | {len(songs)} songs\n")

    played = 0
    skipped = 0

    for i, song in enumerate(songs, 1):
        if not _running:
            break

        # 每首歌播放前也检测客户端
        if i > 1 and not is_client_running():
            print(f"\n[QUIT] 客户端已关闭，剩余 {len(songs) - i + 1} 首跳过")
            break

        result = _play_one(song, i, len(songs))
        if result is None:
            # 客户端关闭
            break
        elif result:
            played += 1
            time.sleep(0.3)
        else:
            skipped += 1

    print(f"\n{'=' * 50}")
    print(f"[FINISH] played {played} | skipped {skipped}")
    print("No temp playlists, no leftovers.")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    if args[0] in ("--random", "-r"):
        count = int(args[1]) if len(args) > 1 else 5
        print(f"Picking {count} random songs from liked...")
        cookies = load_cookies()
        uid = cookies.get("__uid", "")
        if not uid:
            status = get_current_login_status()
            sd = status.get("data", status)
            if sd.get("code") == 200:
                uid = (sd.get("profile", {}).get("userId") or
                       sd.get("account", {}).get("id", ""))
        if not uid:
            print("[ERR] Cannot get user ID")
            sys.exit(1)
        result = get_likelist(uid)
        data = result.get("data", result)
        if data.get("code") != 200:
            print("[ERR] Failed to get liked list")
            sys.exit(1)
        all_ids = data.get("ids", [])
        song_ids = random.sample(all_ids, min(count, len(all_ids)))
        play_sequence(song_ids)

    elif args[0] in ("--daily", "-d"):
        count = int(args[1]) if len(args) > 1 else 10
        print(f"Picking {count} random songs from daily recommendations...")
        r = get_daily_recommendations()
        if not r.get("success") or not r.get("songs"):
            print("[ERR] Failed to get daily recommendations")
            sys.exit(1)
        songs = r["songs"]
        song_ids = [s["id"] for s in (random.sample(songs, min(count, len(songs))))]
        play_sequence(song_ids)

    elif args[0] in ("--playlist", "-p"):
        if len(args) < 2:
            print("[ERR] Please provide playlist ID")
            sys.exit(1)
        pid = args[1]
        r = get_playlist_detail(pid)
        if not r.get("success"):
            print(f"[ERR] Failed to get playlist: {r.get('error')}")
            sys.exit(1)
        song_ids = [s["id"] for s in r["songs"]]
        limit = int(args[2]) if len(args) > 2 else len(song_ids)
        song_ids = song_ids[:limit]
        print(f"Playlist: {r['info']['name']} — {len(song_ids)} songs")
        play_sequence(song_ids)

    else:
        play_sequence(args)


if __name__ == "__main__":
    main()
