# 软件验收记录 · 2026-11-20

六个模块与渠道模型改写补充项均先提交 Spec，再提交单人设计审核，然后实现。对标包见 [完整历史索引与产品取舍](research/decisions.md)。设计审核与作者对稿件的业务验收分别记录。

## 在开发环境中执行的验收

Linux、Python 3.12.14、Django 5.2.19、PostgreSQL 16.2、Node 24.22.3、Chromium Headless Shell 153。除公开 RSS/Atom 实测外，模型及渠道调用使用可控协议响应。浏览器使用独立账号和合成材料。

| 检查 | 实际结果 | 状态 |
|---|---|---|
| 权限 | 匿名读写拒绝；CSRF 验证、登录轮换、停用账号、失败限流、编辑越权审批均有回归 | PASS |
| 证据及来源 | 重复 URL 去重、缺节选补录、本人确认选题。X 分页中断后保留账号水位 | PASS，X 为模拟 |
| 公开订阅 | GitHub 的 PyTorch releases.atom 首次读取 10 条，新增 10 条且均有原文日期；立即重拉读取 10 条，新增 0 条 | PASS，真实 HTTP |
| 生成任务 | 模型协议、缺引用反馈修订、授权次数、断线状态、版本冲突与候选回收 | PASS，受控模型响应 |
| PostgreSQL 并发保存 | 两个独立数据库连接同时写入同一版本，一次成功、一次 409，留下一条新修订 | PASS |
| 渠道交付 | 四端文件可下载；ZIP 中 PNG 可解码；过期渠道稿被拦截；相同版本未知回执不会重复外呼，人工对账恢复远端 ID | PASS，草稿 API 为模拟 |
| 文风规则 | 同稿/同文本不作留出样本，存在退化则挡住上线；旧基线需重评；审批和回滚不影响已入队任务快照 | PASS |
| 浏览器 | 空库登录、收集证据、确认选题、写稿、审批、刷新、四端实际下载。390 px 视口无横向溢出；未出现页面脚本异常 | PASS，SQLite 和 PostgreSQL 各一轮 |
| 运行与恢复 | 迁移空库；含已知业务记录的 PostgreSQL 备份恢复至新库并核对记录；双 Gunicorn 进程下 readiness 和可信代理 Secure CSRF cookie 实测 | PASS，隔离环境 |
| 构建检查 | npm ci、生产构建、Django check、迁移漂移检查、git diff --check | PASS |

后端 `python manage.py test desk` 共 25 项。PostgreSQL 25 项通过，SQLite 24 项通过、1 项 PostgreSQL 专用并发用例跳过。浏览器用例 `python manage.py test tests_ui` 在两套数据库上分别 1/1。部署检查返回 W005、W021，涉及域名子域及 HSTS preload，见 [部署手册](deploy.md)。

走查修复了 RSS 重复枚举、Atom 的 link 选择、填充后表单标签定位、导出触发多余刷新、代理可选依赖缺失。远端 CI 的状态以对应 GitHub Actions 运行记录为准。

## 独立的上线验收

| 项目 | 证据缺口 |
|---|---|
| 真实付费模型、文章质量、本人文风 | MANUAL REVIEW。需授权样本和真实试稿，比对事实出处、改稿时间、是否愿意署名。编号校验无法证明文章的每条事实 |
| X 账号采集、X 和公众号草稿箱 | NOT RUN。需真实权限、预算和封面素材；应在原生草稿箱中确认 ID 和排版 |
| 星球、小红书原生导入 | MANUAL REVIEW。文件导出已验证，实际设备和账号排版仍需核验 |
| agent-autoloop/Hermes 原生集成 | NOT RUN。当前借鉴其运行及学习机制，使用自研持久 worker、回执和文风评测 |
| 实际生产域名、Windows 原生使用、容量与灾备 | NOT RUN。生产部署由部署者实施；按业务峰值进行压测、告警和灾备演练 |
