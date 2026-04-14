# reddit-toolkit

专为独立开发者和出海营销人设计的 Reddit CLI 工具。

不再靠猜测选 subreddit，不再写出被当成垃圾广告删掉的帖子 —— 先深度理解一个社区，再生成真正融入那里的内容。

---

## 核心工作流

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
     pipeline run --product X        scan run / scan daemon
              │                                 │
              ▼                                 ▼
    🔍 自动发现匹配的 Subreddits          🔍 机会推送
    每天更新 · AI 判断适合度          有人在问你能解决的问题
              │                          AI 评分 + 回复草稿
      style learn + rules learn                 │
              │                           notion push
              ▼                                 │
         🧠 社区档案（双重）                     ▼
    写作风格 · 语气 · 标题套路          📋 Notion 数据库
    社群规则 · 禁忌 · 发帖 checklist
              │
     style mimic（自动带入规则）
              │
              ▼
          ✍️ 帖子草稿
    读起来像是社区老用户写的
    不违反社区规则
              │
         自动去 AI 味
              │
              ▼
       ✅ 可直接发布的内容
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

## 自动 Pipeline（推荐入口）

最省事的用法。给一个产品，自动完成「发现 subreddits → 学习风格和规则 → 生成内容 → 推送 Notion」全流程。

```bash
# 运行一次完整 pipeline
reddit-toolkit pipeline run --product myapp

# 定时自动运行（每天一次，挂后台）
reddit-toolkit pipeline daemon --product myapp --interval 1d
```

**pipeline run 每次做的事：**
1. 用 AI 搜索适合这个产品的 subreddits，更新本地追踪列表
2. 对每个 subreddit 学习写作风格（style learn）
3. 学习社群规则和氛围 → 推送到 Notion「Subreddit规则」数据库
4. 生成一篇仿风格帖子（规则约束自动注入 prompt）→ 推送到 Notion「Reddit素材」数据库
5. 下次运行时只处理新增 subreddits 或已过期的缓存，不重复工作

```bash
reddit-toolkit pipeline discover --product myapp   # 只发现 subreddits，不生成内容
reddit-toolkit pipeline list --product myapp       # 查看当前追踪的 subreddits
reddit-toolkit pipeline run --product myapp --dry-run  # 本地预览，不推送 Notion
```

---

## 数据流与定时机制

### 两个 Notion 数据库的关系

```
【本地缓存层】~/.reddit-toolkit/
  rules/{sub}.rules.json     ←── 规则档案（隐性规范7天·官方规则30天过期）
  styles/{sub}.style.json    ←── 写作风格缓存（7天过期）
  tracker/{product}.json     ←── 追踪的 subreddit 列表

        ↓ pipeline run 时读取 rules + style
        ↓ 把规则注入 AI prompt（生成帖子时自动带入约束）

【Notion 层】
  「Subreddit规则」数据库   ←── 每个 subreddit 一条记录，中文内容
                                 包含：整体氛围观察·官方规则·隐性规范·检查清单
  「Reddit素材」数据库      ←── 每次生成的帖子草稿，已按规则约束生成
```

**数据流方向：**
1. `rules learn` → 抓取 Reddit 官方规则 + AI 分析帖子 → 存入本地 `rules/` 缓存
2. `pipeline run` → 读取本地规则缓存 → 注入 AI prompt → 生成帖子 → 推送到「Reddit素材」
3. `pipeline run --push_notion` → 同时把规则档案推送到「Subreddit规则」数据库

### 定时刷新逻辑

| 缓存类型 | 过期时间 | 触发条件 |
|---|---|---|
| 写作风格（style） | 7 天 | style learn / pipeline run |
| 隐性规范（inferred norms） | 7 天 | rules learn / pipeline run |
| 官方侧边栏规则（official rules） | 30 天 | rules learn / pipeline run |

**pipeline run 的完整逻辑（每次执行）：**
```
1. AI 搜索新 subreddits → 追加到追踪列表（已有的不重复添加）
2. 对每个追踪的 subreddit：
   a. 风格缓存未过期 → 直接用；过期 → 重新抓取分析
   b. 规则缓存未过期 → 直接用；过期 → 重新抓取 + AI 重新推断
3. 把规则注入 prompt → 生成帖子
4. 推送规则到「Subreddit规则」Notion 数据库
5. 推送帖子到「Reddit素材」Notion 数据库
```

**daemon 模式**（定时挂后台）：
```bash
reddit-toolkit pipeline daemon --product myapp --interval 1d   # 每天运行一次
reddit-toolkit pipeline daemon --product myapp --interval 8h   # 每8小时运行一次
```
- 启动后立即运行一次，之后按间隔重复
- 每次运行都是完整 pipeline（发现 → 学习 → 生成 → 推送）
- 只有缓存过期的 subreddit 才会重新学习，未过期的直接复用

---

## 第一步 — 告诉工具你在做什么

```bash
# 用文字描述
reddit-toolkit product create --name "MyApp" --description "帮开发者自动生成 API 文档的 CLI 工具"

# 直接读取代码仓库（AI 自己理解产品）
reddit-toolkit product create --name "MyApp" --from-dir ./my-project

# 从网页链接提取（落地页、GitHub、Product Hunt 都行）
reddit-toolkit product create --name "MyApp" --from-url https://myapp.com

reddit-toolkit product list           # 查看所有产品档案
reddit-toolkit product show myapp     # 查看某个档案
```

---

## 第二步 — 找到适合的 Subreddit

```bash
reddit-toolkit style match --product myapp --topic "产品发布"
```

输出带真实订阅人数、自我推广容忍度评级、建议切入角度，末尾直接给出下一步命令。

---

## 第三步 — 深度学习社区（风格 + 规则）

`style learn` 抓取热门帖子，建立写作风格档案，同时自动触发规则学习。

```bash
reddit-toolkit style learn --subreddit SideProject
```

```
Fetching r/SideProject corpus (10 pages)...
  Fetched 243 posts total.
Analyzing writing style with AI...
  Style profile saved for r/SideProject.
Analyzing community rules and norms...
  Rules profile saved for r/SideProject.
```

风格档案 7 天过期，规则档案 7 天过期，官方规则 30 天过期，到期自动刷新。

---

## 社群规则管理

每个 subreddit 的规则档案包含两部分：**官方规则**（从 Reddit API 抓取）+ **AI 观察到的隐性规范**（从帖子内容推断）。全部中文输出。

```bash
reddit-toolkit rules learn --subreddit ClaudeAI           # 手动学习
reddit-toolkit rules learn --subreddit ClaudeAI --notion  # 学完推送 Notion
reddit-toolkit rules learn --subreddit ClaudeAI --force   # 强制刷新
reddit-toolkit rules list                                  # 查看所有缓存
reddit-toolkit rules show --subreddit ClaudeAI            # 查看完整档案

# 配置推送目标（Notion 数据库 ID）
reddit-toolkit rules notion-setup --page-id <NOTION_DATABASE_ID>
```

**规则档案内容：**
- 🌐 整体氛围观察 — AI 阅读帖子后总结的社群性格
- 📋 官方规则 — 侧边栏写明的规则
- 🎯 社群氛围与价值观
- 🚫 会被删除的内容
- ✅ 发帖前检查清单（to-do 格式）
- 💡 安全发帖角度
- 🔗 外链规则

生成内容时，规则自动注入到 AI prompt，帖子不会违反社区规定。

---

## 第四步 — 生成融入社区的帖子

```bash
reddit-toolkit style mimic --subreddit SideProject --product myapp --topic "产品发布"
reddit-toolkit style mimic --subreddit SideProject --product myapp --notion  # 推送 Notion
```

自动加载该 subreddit 的规则缓存，生成后自动去 AI 味。

---

## 持续扫描机会

扫描器监控 subreddit，找出有人在问你产品能解决的问题的帖子。

```bash
reddit-toolkit scan run --product myapp --dry-run
reddit-toolkit scan daemon --product myapp --interval 8h
reddit-toolkit scan run --product myapp --notion
```

---

## Notion 集成

```bash
export NOTION_TOKEN=secret_...

# 绑定「Reddit素材」数据库（存放帖子草稿和扫描机会）
reddit-toolkit notion setup --product myapp --database-id <ID>

# 绑定「Subreddit规则」数据库（存放规则档案）
reddit-toolkit rules notion-setup --page-id <DATABASE_ID>
```

绑定后，`pipeline run`、`scan run --notion`、`style mimic --notion` 全部自动推送。

---

## 其他命令

```bash
# 浏览内容
reddit-toolkit content hot --subreddit python --limit 20
reddit-toolkit content search "api documentation"

# 探索 subreddit
reddit-toolkit subs search "developer tools"
reddit-toolkit subs info rust

# AI 写作辅助
reddit-toolkit write title --subreddit webdev --topic "我的新 CLI 工具"
reddit-toolkit write body --subreddit webdev --title "Show HN 风格的帖子"
reddit-toolkit write comment --post-title "API 设计最佳实践？" --tone supportive
```

---

## 环境变量

| 变量 | 是否必须 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 必须 | 驱动所有 AI 功能 |
| `REDDIT_TOOLKIT_MODEL` | 可选 | 指定 Claude 模型（默认：`claude-opus-4-5`） |
| `NOTION_TOKEN` | 可选 | 推送结果到 Notion |
| `REDDIT_CLIENT_ID` | 可选 | 启用 PRAW，获取更丰富的语料（含评论） |
| `REDDIT_CLIENT_SECRET` | 可选 | 与 `REDDIT_CLIENT_ID` 配合使用 |

---

## 本地数据存储

```
~/.reddit-toolkit/
  profiles/     # 产品档案
  styles/       # subreddit 写作风格缓存（7天TTL）
  rules/        # subreddit 规则档案（规范7天·官方规则30天TTL）
  tracker/      # pipeline 追踪的 subreddits（per product）
  state/        # 扫描历史（去重 + 机会日志）
  notion/       # Notion 数据库绑定缓存
```

```bash
export REDDIT_TOOLKIT_DATA_DIR=/your/path  # 自定义存储路径
```

---

## License

MIT
