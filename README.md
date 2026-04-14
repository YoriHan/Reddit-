# reddit-toolkit

专为独立开发者和出海营销人设计的 Reddit CLI 工具。

不再靠猜测选 subreddit，不再写出被当成垃圾广告删掉的帖子 —— 先深度理解一个社区，再生成真正融入那里的内容。

---

## 核心工作流

Reddit 对外来者非常敏感。每个社区都有自己的语气、词汇习惯和对自我推广的容忍度。整个工具围绕四步流程设计：

```
                       📦 你的产品
               文字描述 · 代码仓库 · 网页链接
                            │
                   product create
                            │
                            ▼
                       🗂️ 产品档案
               名称 · 目标用户 · 功能 · 关键词
                            │
              ┌─────────────┴──────────────────┐
              │                                 │
     style match --topic             scan run / scan daemon
              │                                 │
              ▼                                 ▼
    🎯 匹配的 Subreddit 列表              🔍 机会推送
    按匹配度排名 · 真实订阅人数       有人在问你能解决的问题
    自我推广容忍度 · 建议切入角度      AI 评分 + 回复草稿
              │                                 │
        style learn                       notion push
              │                                 │
              ▼                                 ▼
         🧠 社区风格档案                  📋 Notion 数据库
    语气 · 标题套路 · 高频词汇
              │
        style mimic
              │
              ▼
          ✍️ 帖子草稿
    读起来像是社区老用户写的
              │
         自动去 AI 味
              │
              ▼
       ✅ 可直接发布的内容
    无明显 AI 写作痕迹
```

---

## 安装

```bash
pip install reddit-toolkit
```

或从源码安装：

```bash
git clone https://github.com/YoriHan/Reddit-
cd Reddit-
pip install -e .
```

**必须：** 需要 [Anthropic API Key](https://console.anthropic.com/) 才能使用所有 AI 功能。

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## 第一步 — 告诉工具你在做什么

创建一个产品档案。这是 AI 后续所有分析的基础 —— 它需要知道你在做什么、给谁用。

**用文字描述：**
```bash
reddit-toolkit product create --name "MyApp" --description "帮开发者自动生成 API 文档的 CLI 工具"
```

**直接读取代码仓库（AI 自己理解你的产品）：**
```bash
reddit-toolkit product create --name "MyApp" --from-dir ./my-project
```

**从网页链接提取（落地页、博客文章、Product Hunt 页面都行）：**
```bash
reddit-toolkit product create --name "MyApp" --from-url https://myapp.com
```

AI 会自动提取产品描述、解决的问题、目标用户、核心功能和关键词，保存为可复用的档案。

```bash
reddit-toolkit product list           # 查看所有已保存的产品档案
reddit-toolkit product show myapp    # 查看某个档案的详细内容
```

---

## 第二步 — 找到适合的 Subreddit

不要靠猜。用 `style match` 让 AI 根据你的产品和发帖主题，找出真正欢迎你出现的社区 —— 带真实订阅人数，还有对自我推广的容忍度评级。

```bash
reddit-toolkit style match --product myapp --topic "产品发布"
```

```
Finding best subreddits for: 产品发布...

Top 5 subreddits for "产品发布":

  1. r/SideProject — 142,000 subscribers
     Why: 专门给独立开发者分享作品的社区
     Self-promo: high
     Angle: 聊你遇到的问题和做这个东西的过程

  2. r/webdev — 980,000 subscribers
     Why: 开发者会讨论能提升工作效率的工具
     Self-promo: medium
     Angle: 先聊技术挑战，自然带出工具

  3. r/programming — 6,200,000 subscribers
     Why: 受众很大但对营销很警惕，要用内容说话
     Self-promo: low
     Angle: 写架构决策，而不是产品介绍

  ...

Next steps:
  reddit-toolkit style learn --subreddit SideProject
  reddit-toolkit style mimic --subreddit SideProject --product myapp --topic "产品发布"
```

输出末尾直接给出下一步要运行的命令，不用自己想。

---

## 第三步 — 彻底学习这个社区的写法

这是大多数人跳过的一步，也是帖子被踩的根本原因。

`style learn` 会抓取该 subreddit 的数百篇热门帖子，然后用 AI 建立风格档案：这个社区的语气是什么、什么样的标题格式有效、哪些词汇能让你显得像本地人、他们对自我推广的容忍度。

```bash
reddit-toolkit style learn --subreddit SideProject
```

```
Fetching r/SideProject corpus (10 pages)...
  Fetching page 1/10...
  Fetching page 2/10...
  ...
  Fetched 243 posts total.
Analyzing writing style with AI...

Style profile saved for r/SideProject.
  Tone: 随意、第一人称、讲故事
  Self-promo tolerance: high
  Title patterns: 7 种已识别
  Vocabulary signals: shipped, built, months, feedback, free
```

风格档案会缓存在本地，下次用不需要重新抓取。

```bash
reddit-toolkit style list                              # 查看所有已缓存的风格档案
reddit-toolkit style show --subreddit SideProject    # 查看完整分析内容
```

**进阶：用 PRAW 获取更丰富的风格数据**

如果你有 Reddit API 凭据，工具还会额外抓取热门帖子的评论区 —— 让 AI 更深入地理解这个社区的人实际上怎么说话。

```bash
export REDDIT_CLIENT_ID=your_id
export REDDIT_CLIENT_SECRET=your_secret
reddit-toolkit style learn --subreddit SideProject   # 检测到环境变量后自动启用
```

---

## 第四步 — 生成一篇真正融入社区的帖子

现在写。AI 把你的产品档案和社区风格档案结合起来，生成一篇读起来像社区老用户写的帖子。生成完成后会自动经过一轮去 AI 味处理，消除"leverage""seamless""fostering"之类明显的 AI 写作痕迹，不需要手动触发。

```bash
reddit-toolkit style mimic --subreddit SideProject --product myapp --topic "产品发布"
```

```
╭─ Mimic Post for r/SideProject ──────────────────────────────────╮
│                                                                  │
│ TITLE: 花了 3 个月做了一个我一直想要的 API 文档工具，终于发布了  │
│                                                                  │
│ 潜水了很久，终于有东西可以分享了。                               │
│                                                                  │
│ 我在工作中写了很多内部工具，最让我崩溃的一直是文档这件事...      │
│                                                                  │
╰──────────────────────────────────────────────────────────────────╯
```

**没有保存产品档案？直接用描述：**
```bash
reddit-toolkit style mimic --subreddit SideProject --describe "给开发者用的 API 文档生成工具"
```

**用 --topic 控制发帖角度：**
```bash
reddit-toolkit style mimic --subreddit SideProject --product myapp --topic "招募内测用户"
```

**查看 AI 为什么认为这篇帖子合适：**
```bash
reddit-toolkit style mimic --subreddit SideProject --product myapp --verbose
```

---

## 持续运行 — 扫描机会

产品档案配置好之后，扫描器会持续监控你关注的 subreddit，找出那些有人在问你产品能解决的问题的帖子。

```bash
reddit-toolkit scan run --product myapp --dry-run
```

```
Scan summary:
  Subreddits scanned: 5
  Posts fetched: 247
  New posts scored: 189
  Opportunities found: 3

  [8/10] "有没有能自动生成文档的工具？"
  Hook: 直接痛点，用户在主动找解决方案
  Draft title: "我做了一个专门解决这个的工具..."

  [7/10] "你们团队怎么处理 API 文档的？"
  Hook: 常见抱怨，适合自然带出工具
  Draft title: "我们以前也有同样的问题，后来..."
```

**定时自动运行（不需要配置 cron）：**
```bash
reddit-toolkit scan daemon --product myapp --interval 8h
```

**或者生成一行 crontab 配置：**
```bash
reddit-toolkit scan setup-cron --product myapp --hour 9 --minute 0
```

**结果推送到 Notion：**
```bash
export NOTION_TOKEN=secret_...
reddit-toolkit notion setup --product myapp
reddit-toolkit scan run --product myapp --notion
```

推送到 Notion 的每一条帖子草稿都已经自动完成去 AI 味处理，可以直接复制使用。

---

## 其他命令

**不依赖产品档案，直接浏览 Reddit：**

```bash
# 浏览内容
reddit-toolkit content hot --subreddit python --limit 20 --verbose
reddit-toolkit content top --subreddit startups --time week
reddit-toolkit content search "api documentation" --sort relevance

# 探索 subreddit
reddit-toolkit subs search "developer tools"
reddit-toolkit subs explore "productivity"
reddit-toolkit subs info rust

# AI 写作辅助（不需要产品档案）
reddit-toolkit write title --subreddit webdev --topic "我的新 CLI 工具"
reddit-toolkit write body --subreddit webdev --title "Show HN 风格的帖子"
reddit-toolkit write comment --post-title "API 设计有什么最佳实践？" --tone supportive
```

---

## 环境变量配置

| 变量 | 是否必须 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 必须 | 驱动所有 AI 功能（风格分析、帖子生成、机会评分、去 AI 味） |
| `REDDIT_TOOLKIT_MODEL` | 可选 | 指定使用的 Claude 模型（默认：`claude-opus-4-5`） |
| `NOTION_TOKEN` | 可选 | 把扫描结果推送到 Notion 数据库 |
| `REDDIT_CLIENT_ID` | 可选 | 启用 PRAW，获取更丰富的风格数据（含评论语料） |
| `REDDIT_CLIENT_SECRET` | 可选 | 与 `REDDIT_CLIENT_ID` 配合使用 |
| `REDDIT_USER_AGENT` | 可选 | 自定义 PRAW User Agent（默认：`reddit-toolkit/1.0`） |

内容发现、subreddit 查询等只读功能使用 Reddit 公开 JSON API，不需要任何凭据。

---

## 本地数据存储

产品档案和扫描状态存储在 `~/.reddit-toolkit/`：

```
~/.reddit-toolkit/
  profiles/     # 产品档案
  styles/       # 缓存的 subreddit 风格分析
  state/        # 扫描历史（去重 + 机会日志）
```

自定义存储路径：
```bash
export REDDIT_TOOLKIT_DATA_DIR=/your/path
```

---

## 参与贡献

欢迎提 Issue 和 PR。代码是纯 Python，没有复杂框架，核心依赖只有 `requests`、`anthropic` 和 `rich`。

```bash
git clone https://github.com/YoriHan/Reddit-
cd Reddit-
pip install -e .
pip install pytest
pytest
```

---

## License

MIT
