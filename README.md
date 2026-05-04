<p align="center">
  <img src="logo.png" width="128" alt="Cloud Music MCP Logo">
</p>

# Cloud Music MCP

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)](https://github.com/longhz/cloud-music-mcp/pulls)

**为 AI Agent 插上音乐的翅膀 — 网易云音乐 MCP Server**

通过自然语言，让 Claude Code、Claude Desktop 等 AI Agent 帮你：
搜歌、播放、下载、获取每日推荐、管理歌单、浏览评论 — 完整的网易云音乐体验。

## 架构

```
┌──────────────┐     ┌─────────────────┐     ┌────────────────┐
│  AI Agent    │────▶│  Python MCP     │────▶│  Node.js Proxy  │
│  (Claude)    │     │  (FastMCP)      │     │  (port 36530)   │
└──────────────┘     └─────────────────┘     └───────┬────────┘
                                                     │ WEPI 加密
                                                     ▼
                                            ┌────────────────┐
                                            │  网易云音乐 API  │
                                            └────────────────┘
```

- **Python 端**：FastMCP 服务器，定义 MCP 工具，纯 HTTP 转发，无加密逻辑
- **Node.js 代理**：`@neteasecloudmusicapienhanced/api`，本地运行在 127.0.0.1:36530，自动处理 WEPI 加密（AES + RSA）
- **播放唤起**：`orpheus://` URL Scheme → 网易云音乐桌面客户端
- **认证**：扫码登录，Cookies 仅存储在本地 `storage/cookies.json`（已 gitignore）

## 功能

- 扫码登录 / 手机验证码登录 / 登出
- 搜索歌曲 / 歌手 / 专辑
- 获取每日推荐 / 私人 FM / 推荐歌单 / 排行榜
- 查看 / 管理用户歌单（创建的和收藏的）
- 获取歌曲详情 / 歌词 / 播放 URL
- 喜欢 / 取消喜欢歌曲，查看红心列表
- 相似歌曲推荐
- 歌曲 / 歌单 / 专辑评论
- 歌手详情 / 热门歌曲 / 专辑 / MV
- 专辑详情 / 新碟上架
- MV 详情 / 播放链接 / 推荐 MV
- 用户收藏计数 / VIP 信息
- **下载歌曲**（9 级音质，自动回退）
- **播放歌曲 / 歌单 / MV / 专辑**（唤起桌面客户端）

## 前置条件

| 依赖 | 说明 |
|------|------|
| Python 3.10+ | MCP 服务器运行环境 |
| Node.js 16+ | API 代理运行环境（处理加密） |
| 网易云音乐客户端 | 播放唤起（可选，不影响其他功能） |
| LLM 客户端 | Claude Desktop / Claude Code 等 |

## 快速开始

### 1. 克隆并安装

```bash
git clone https://github.com/longhz/cloud-music-mcp.git
cd cloud-music-mcp

# 安装 Node.js 代理依赖
npm install

# 安装 Python 依赖
pip install -e .
```

### 2. 配置 MCP 客户端

**Claude Desktop**（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "cloud-music": {
      "command": ["python", "-m", "cloud_music_mcp"],
      "cwd": "H:/dev/cloud-music-mcp/src",
      "enabled": true
    }
  }
}
```

> 将 `cwd` 替换为你的项目实际路径。

**Claude Code**（项目 `.mcp.json` 或全局配置）：

```json
{
  "mcpServers": {
    "cloud-music": {
      "command": "python",
      "args": ["-m", "cloud_music_mcp"],
      "cwd": "/path/to/cloud-music-mcp/src"
    }
  }
}
```

### 3. 登录

重启 LLM 客户端后，在对话中输入：

> "帮我登录网易云音乐"

AI 会调用 `cloud_music_login` 弹出二维码，用手机网易云音乐 App 扫码即可。登录状态持久化，无需重复登录。


## 完整工具列表

### 登录认证

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_login` | - | 弹出二维码，扫码登录 |
| `cloud_music_phone_login` | `phone`, `captcha`, `countrycode` | 手机验证码登录 |
| `cloud_music_send_captcha` | `phone`, `countrycode` | 发送验证码 |
| `cloud_music_status` | - | 检查登录状态 |
| `cloud_music_logout` | - | 退出登录 |

### 歌单

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_my_playlists` | - | 我的歌单列表 |
| `cloud_music_playlist_detail` | `playlist_id` | 歌单详情（含歌曲列表） |
| `cloud_music_playlist_all` | `playlist_id`, `limit` | 歌单全部歌曲 |

### 歌曲

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_song_detail` | `song_id` | 歌曲详情 |
| `cloud_music_song_url` | `song_id`, `level` | 获取播放 URL（9 级音质） |
| `cloud_music_lyric` | `song_id` | 获取歌词 |
| `cloud_music_like` | `song_id`, `like` | 喜欢/取消喜欢 |
| `cloud_music_likelist` | - | 红心歌曲列表 |
| `cloud_music_simi_song` | `song_id` | 相似歌曲推荐 |

### 搜索与推荐

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_search` | `keyword`, `limit` | 搜索歌曲 |
| `cloud_music_daily_recommend` | - | 每日推荐 30 首 |
| `cloud_music_personal_fm` | - | 私人 FM |
| `cloud_music_recommend_playlists` | `count` | 推荐歌单 |
| `cloud_music_toplist` | - | 排行榜 |

### 歌手

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_artist_detail` | `artist_id` | 歌手详情 |
| `cloud_music_artist_top_songs` | `artist_id`, `limit` | 歌手热门歌曲 |
| `cloud_music_artist_albums` | `artist_id`, `limit` | 歌手专辑列表 |
| `cloud_music_artist_mvs` | `artist_id`, `limit` | 歌手 MV 列表 |

### 专辑

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_album_detail` | `album_id` | 专辑详情 |
| `cloud_music_album_new` | - | 新碟上架 |

### MV

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_mv_detail` | `mv_id` | MV 详情 |
| `cloud_music_mv_url` | `mv_id`, `quality` | MV 播放链接 |
| `cloud_music_mv_recommend` | - | 推荐 MV |

### 评论

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_comment_song` | `song_id`, `limit` | 歌曲评论 |
| `cloud_music_comment_playlist` | `playlist_id`, `limit` | 歌单评论 |
| `cloud_music_comment_album` | `album_id`, `limit` | 专辑评论 |

### 下载

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_download` | `song_id`, `level`, `save_dir` | 下载歌曲到本地 |
| `cloud_music_vip_info` | - | 黑胶VIP 信息 |

### 播放

| 工具 | 参数 | 说明 |
|------|------|------|
| `cloud_music_play` | `id`, `type` | 播放歌曲/歌单/MV/专辑 |
| `cloud_music_user_subcount` | - | 用户收藏计数 |

## 音质等级

| 等级 | 标签 | 典型码率 | 要求 |
|------|------|----------|------|
| `standard` | 标准 | 128 kbps | - |
| `higher` | 较高 | 192 kbps | - |
| `exhigh` | 极高 | 320 kbps | - |
| `lossless` | 无损 | ~900 kbps | VIP |
| `hires` | Hi-Res | ~2000 kbps | VIP |
| `jyeffect` | 高清环绕声 | ~4000 kbps | 黑胶SVIP |
| `sky` | 沉浸环绕声 | ~4000 kbps | 黑胶SVIP |
| `dolby` | 杜比全景声 | ~6000 kbps | 黑胶SVIP |
| `jymaster` | 超清母带 | ~6000 kbps | 黑胶SVIP |

若请求的音质不可用，下载功能会自动线性回退到可用音质。


## 使用示例

### 自然语言（通过 AI Agent）

```
"播放我红心歌单里的随机一首歌"
"下载周杰伦的晴天无损音质"
"今天有什么新歌推荐？"
"搜一下 Taylor Swift 的歌"
"看看这首歌的评论"
"我的VIP什么时候到期？"
"播放每日推荐"
```

### 命令行直接调用

```bash
# 检查登录状态
python -c "
import sys; sys.path.insert(0,'src')
from cloud_music_mcp.api import check_login_status
print(check_login_status())
"
```

见 [SKILL.md](./SKILL.md) 获取更多命令行用法示例。


## 项目结构

```
cloud-music-mcp/
├── src/cloud_music_mcp/
│   ├── __init__.py          # 包入口
│   ├── __main__.py          # python -m cloud_music_mcp
│   ├── main.py              # FastMCP 服务器 + ~37 个工具
│   ├── api.py               # 核心 API 封装（35+ 函数）
│   ├── auth.py              # 登录认证
│   ├── server.py            # Node.js 代理生命周期管理
│   └── storage/             # cookies 存储（已 gitignore）
├── node_modules/            # Node.js 代理依赖
├── package.json             # Node.js 代理配置
├── pyproject.toml           # Python 项目配置
├── logo.png                 # Logo
├── LICENSE
└── README.md
```

## 安全与隐私

- 登录凭证（Cookies）**仅存储在本地** `storage/cookies.json`，已通过 `.gitignore` 排除
- Node.js 代理**仅监听 127.0.0.1:36530**，不暴露到网络
- 所有 API 请求的 WEPI 加密由本地代理处理，不依赖第三方服务

## FAQ

**Q: 为什么不直接用 pyncm？**
A: [pyncm](https://github.com/greats3an/pyncm) 已从 PyPI 下架。本项目使用 Node.js 代理方案，由社区维护的 `@neteasecloudmusicapienhanced/api` 包处理加密，更稳定可靠。

**Q: 下载功能需要什么权限？**
A: 标准/较高/极高音质不需要 VIP。无损及以上需要黑胶VIP，环绕声/杜比/母带需要黑胶SVIP。

**Q: 播放唤起不工作？**
A: 确保网易云音乐桌面客户端已安装并运行。Windows 路径通常为 `D:\Program Files\NetEase\CloudMusic\cloudmusic.exe`。

**Q: 如何切换账号？**
A: 先 `cloud_music_logout`，再 `cloud_music_login` 重新扫码。

## License

MIT © [longhz](https://github.com/longhz)
