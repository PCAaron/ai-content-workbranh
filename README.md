# 笺台 · AI 自媒体编辑工作台

为一个编辑部提供从采集到草稿交付的私有工作台。外部材料提供事实背景，作者本人确认的原话决定写作角度。React 前端与 Python/Django API 同源，生成任务由独立 Python worker 执行。生产数据库使用 PostgreSQL，单机试用支持 SQLite。

[参考项目的迭代过程](docs/research/decisions.md) · [架构](docs/architecture.md) · [模块 Spec](docs/specs) · [设计审核](docs/reviews) · [部署与恢复手册](docs/deploy.md) · [验收记录](docs/acceptance.md)

## 本机启动

准备 Python 3.12、Node 24、npm，以及可用于图卡的中文字体。在仓库根目录执行：

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
python manage.py migrate
python manage.py account chief reviewer
python manage.py runserver 127.0.0.1:8000
```

打开 http://127.0.0.1:8000/ ，使用刚创建的账号登录。密码通过交互设置。独立编辑账号用 `python manage.py account writer editor` 创建。PowerShell 可使用 `py -3.12 -m venv .venv`，随后以 `.\.venv\Scripts\python.exe` 执行各条 Python 命令。Windows 用户需将 PRESS_CJK_FONT 指向已安装的中文字体文件。

## 完成第一篇稿件

1. **来源材料**。录入文章标题、链接、署名和节选。只有链接时可先保存，以同一 URL 再次提交节选即可补全。已配置的 RSS/Atom、X 账号可按需拉取。
2. **本人原话与选题**。记录原话及出处，确认归属后关联至少一条外部来源。编辑页并排展示母稿、原话和来源。
3. **母稿编辑**。手写或明确授权模型起稿。用 `[S编号]` 标注来源并保留本人引语。可以从同作者已审核稿选择风格样本。批注与修订关联具体版本，恢复历史时追加新版本。
4. **渠道转换**。审核当前母稿，生成各平台的可编辑版本。可再授权模型按平台特点改写。审核渠道稿后导出或显式创建远端草稿。母稿更新后需基于新版本重新生成。
5. **文风实验室**。从人工改稿提取候选措辞，用不同文章的人工修订对照基线。至少一篇改善且没有样本退化后，审核员可启用规则。任务保存文风快照，规则支持回滚。

| 渠道 | 交付文件 | 可选外部操作 |
|---|---|---|
| 微信公众号 | HTML 文章及来源 | 官方接口创建草稿，需账号权限与有效封面素材 ID |
| X Articles | 长文 TXT | 使用具备相应权利的用户访问令牌创建长文草稿 |
| 知识星球 | Markdown | 人工导入目标星球 |
| 小红书 | 配文、来源、可编辑图卡 JSON、1080×1440 PNG 组成的 ZIP | 在原生 App 内确认顺序与排版 |

无外部凭证可走通人工写作、审核和文件导出。启用模型后，在第二个终端加载与 Web 相同的环境，运行 `python manage.py worker`。模型和平台令牌只配置在服务端。

## 可复现检查

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test desk
python -m pip install -r requirements-test.txt
python -m playwright install chromium
python manage.py test tests_ui
```

浏览器用例需要先构建 web/dist，使用临时测试库和合成材料。可用 CHROMIUM_BIN 指定现有 Chromium 程序。生产用 PostgreSQL 的并发测试需要独立测试数据库；生产应用账号无需创建测试库的权限。
