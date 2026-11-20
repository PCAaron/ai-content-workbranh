# Python 部署、验收与恢复

部署方选择域名、数据库、TLS 入口、模型与平台账号。一套部署对应一个编辑部，成员共享素材及稿件。不同客户使用独立部署和数据库。以下示例以 Linux 为生产运行环境。

## 1. 运行组件与依赖

| 组件 | 职责 | 运行要求 |
|---|---|---|
| HTTPS 反向代理 | TLS、入口限流、请求体上限、可信协议头 | 域名流量仅转给私网或本机 Web |
| Gunicorn 与 Django | React 静态资源、会话、业务 API、显式采集和草稿交付 | 持久进程，使用专用非 root 账户 |
| Python worker | 领取已授权模型任务、记录回执、验证并有限复写 | 独立守护，与 Web 共享数据库 |
| PostgreSQL | 账号、会话、素材、选题、版本、任务、审核和反馈 | 已在 16 上测试；准备专用数据库与角色 |

准备 Python 3.12、Node 24 和能渲染中文的 TTF/OTF/TTC。Node 仅构建时使用，发布包需保留 web/dist。Gunicorn 示例用于 Linux。Windows 本机运行见 README。

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
```

## 2. 注入环境

根目录 .env.example 提供名称和示例。程序直接读进程环境。Web 和 worker 分别由进程管理器加载同一份受保护配置，权限仅开放给服务账号。使用 shell 时可对可信配置文件执行：

```bash
set -a
. /etc/folio/folio.env
set +a
```

| 参数 | 用法 |
|---|---|
| PRESS_ENV、PRESS_SECRET、PRESS_HOSTS | 生产填 production；签名密钥至少 50 字符，独立随机生成；HOSTS 仅填真实域名，多个域名以逗号相连 |
| PGDATABASE、PGUSER、PGPASSWORD、PGHOST、PGPORT | PostgreSQL 数据库和角色。跨主机连接按服务商要求配置 PGSSLMODE=verify-full 与 CA。迁移角色需要 DDL 权限，应用角色需要表与序列读写权限 |
| PRESS_TRUST_TLS_PROXY | 只有确保代理会覆盖 X-Forwarded-Proto，且外部无法直连应用端口时，才设 1 |
| PRESS_CJK_FONT | 已授权使用的中文字体文件路径。缺字体时图卡导出返回明确错误 |
| PRESS_FEEDS | 运营者认可的 HTTPS RSS/Atom 地址构成的 JSON 映射。手工粘贴链接只存储出处。公众号可用有权接入的订阅或手工节选 |
| PRESS_X_ACCOUNTS、PRESS_X_READ_TOKEN | 逗号分隔的 X 账号及读取令牌，按账号推进游标。使用近期搜索，窗口、价格和额度以账号为准 |
| PRESS_MODEL_URL、PRESS_MODEL、PRESS_MODEL_KEY | 完整 HTTPS Chat Completions 端点（含路径）、模型与密钥。要求支持 messages、max_tokens 和 choices[].message.content。调用时向选定服务商传输材料、本人原话、批注及显式选取的风格样本 |
| PRESS_X_DRAFT_TOKEN | 有权创建 X Articles 草稿的用户令牌，与采集令牌独立。运维方负责刷新或轮换 |
| PRESS_WX_APP_ID、PRESS_WX_SECRET、PRESS_WX_COVER_ID | 公众号凭证和已上传的有效封面素材 ID，核对出口 IP 和账号权限。每个获批渠道版本对应一次独立建稿意图 |
| HTTPS_PROXY、SSL_CERT_FILE | 有出网代理时配置可信 CA。代理与应用日志不应收集凭证、请求正文或带 token 的查询串 |

可在部署者终端使用 Python secrets.token_urlsafe(64) 生成签名密钥，并直接转存至密钥管理器。不要复用仓库示例值。

## 3. 迁移、账号与启动

```bash
python manage.py migrate --noinput
python manage.py migrate --check
python manage.py check --deploy
python manage.py account chief reviewer
python manage.py account writer editor
```

编辑可保存修订与授权生成。确认原话与关联选题绑定到原话作者。审核员额外可批准母稿和渠道版、导出、建平台草稿、对账、启用与回滚规则。审核员也可参与写作；组织要求双人复核时，需分配给不同实际人员。重设密码用 changepassword；停用账户可在 Django 管理 shell 修改该用户的 is_active。

分别托管下面两个前台进程：

```bash
.venv/bin/gunicorn press.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 90 --graceful-timeout 75
```

```bash
.venv/bin/python manage.py worker
```

两者均以仓库构建目录为工作目录。配置 systemd、容器或现有进程管理器分别重启失败进程。停止 worker 时先发 SIGTERM 并预留至少 90 秒。强制中止后，过期的调用中任务会被记为待核实。

HTTPS 入口可用 Nginx。向回环地址转发 Host 和由本代理写入的 X-Forwarded-Proto，将 client_max_body_size 设为 256k，统一处理 HTTP 转 HTTPS。应用启用 Secure cookie 和主机级 HSTS。check --deploy 对子域 HSTS 和 preload 给出 W005/W021，需要域名所有者独立判断。

## 4. 上线核验与常见状态

1. 通过实际 HTTPS 域访问 /health/ready，预期 HTTP 200 和 ready。另用一条获授权的测试任务确认 worker 正常领取并给出结果。
2. 两个角色各自登录，走一遍 README 的素材、母稿和审核过程。两个窗口对同一旧版分别保存，第二次应收到 409。
3. 同一 RSS 连拉两次，第二次的已有 URL 应不再新增。检查 X 每账号水位及本轮是否还有下一页。
4. 导出四端文件，检查原文链接、PNG 图中文字和顺序。按对应平台流程核对实际 App/后台排版。
5. 队列一直 queued 时先查 worker 和数据库；failed 检查服务商授权或校验原因；unknown 先核对提供商回执。conflict 的候选可从运行记录取回，人工比对后保存。相同目标版本重复请求会返回原任务。
6. 平台建稿 unknown，或 sending 超过五分钟时，由审核员到真实平台草稿箱查证，在“运行记录 → 平台回执”登记草稿 ID 或核实为空的理由。最终公开发表在平台原生界面由作者决定。
7. 用不同文章评测措辞。核对样本分数、语义、事实与作者实际改稿成本，再启用或回滚规则。

## 5. 备份、恢复和回退

升级前记录部署提交、迁移状态与环境参数名。频率、保留期、备份加密、访问权限和恢复时间目标由运维方制定。以下命令使用已注入的 PostgreSQL 管理连接参数，在新建隔离库演练：

```bash
pg_dump --format=custom --file=folio-backup.dump "$PGDATABASE"
createdb folio_restore_check
pg_restore --no-owner --exit-on-error --dbname=folio_restore_check folio-backup.dump
PGDATABASE=folio_restore_check python manage.py migrate --check
```

抽查恢复库中的正文、版本、审批、平台回执及文风规则，与原库对应记录比对。密钥和服务配置单独备份。升级先在恢复副本验迁移和应用。回退优先选择兼容当前 schema 的前一构建；确需数据库回退时先另建数据库恢复，评估新写入后再切流。

当前默认共享一个编辑部，未内置组织 SSO、多租户或集群级预算。现场容量、灾备、真实模型质量、渠道权限和发布责任见 [验收记录](acceptance.md)。

参考：[Django 部署核对](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) · [PostgreSQL 备份](https://www.postgresql.org/docs/16/app-pgdump.html) · [X 近期搜索](https://docs.x.com/x-api/posts/search/quickstart/recent-search) · [X Articles 草稿](https://docs.x.com/x-api/articles/create-draft-article) · [公众号草稿](https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html)。

## 跨账号主题发现

部署端应用 0007 迁移（python manage.py migrate），构建 React 并重新加载 Web 进程。两个检索服务可独立启用；此功能由编辑在网页中手动触发，无需运行 worker。

| 平台 | Web 进程变量 | 服务与权限 | 一次检索 |
|---|---|---|---|
| X | PRESS_X_READ_TOKEN | 可使用 X API v2 recent search 的 Bearer Token，账号须有可用额度 | 请求 api.x.com 一页，近七天，按最新抓取 10/20/50 条以内，再在样本内按公开互动排序 |
| 微信公众号公开文章 | PRESS_BRAVE_SEARCH_KEY | Brave Web Search 订阅密钥；检索目标为 mp.weixin.qq.com，搜索语言为简体中文 | 请求 api.search.brave.com 一页，上限 10/20；近一周筛选使用索引判断的页面年龄，可能取自发布或更新时间 |

服务按各自的账户方案计费。按主题检索无需配置 PRESS_X_ACCOUNTS、PRESS_FEEDS 或公众号投递凭证。部署方可在供应商控制台核对权限、额度及其数据使用条件。密钥只在服务端读取，浏览器使用同源会话。

在「素材与选题 → 主题发现」输入一个公开话题。可对照 X 原帖查看采样时刻的互动字段；数值随后可能变化。公众号可点击原文，核对标题并填写可引用节选。该平台的网页检索摘要只在本轮预览中出现。样本可能少于上限或为空；微信端的阅读、点赞和全平台覆盖率均未知。

预览入库凭据有效期为 30 分钟。每次检索在 desk_discoveryrun 留下请求号、操作者、时间、平台、上限及处理结果。同一请求号重放返回 409。进程中断可能留下 pending，可按采样时间核对供应商用量后由编辑决定是否发起新检索。接口不自动重试或翻页。
