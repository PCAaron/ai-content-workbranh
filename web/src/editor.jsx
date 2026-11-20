import React, { useState } from "react";
import { ArrowLeft, Feather, History, Link2 } from "lucide-react";
import { api, platformNames, stateNames } from "./api";
import {
  Header,
  Btn,
  Field,
  Empty,
  useApp,
  useLoad,
  Load,
  dataOf,
  Pill,
  Link,
} from "./ui";

export function Manuscripts() {
  const { stamp } = useApp(),
    rec = useLoad("drafts", stamp);
  return (
    <>
      <Header
        title="稿件工作区"
        desc="从确认过的选题起稿。母稿、修订与渠道版本在此留存。"
      />
      <section className="panel">
        <Load record={rec}>
          {(rows) =>
            rows.length ? (
              rows.map((x) => (
                <a key={x.id} href={"#draft/" + x.id} className="row">
                  <div>
                    <small>母稿 #{x.id}</small>
                    <h3>{x.topic__title}</h3>
                  </div>
                  <Pill>
                    {x.approved ? "审核通过" : x.version ? "待审核" : "待起稿"}
                  </Pill>
                </a>
              ))
            ) : (
              <Empty title="尚无稿件">
                <a href="#library">前往素材与选题 →</a>
              </Empty>
            )
          }
        </Load>
      </section>
    </>
  );
}
export function Editor({ id }) {
  const { stamp } = useApp(),
    rec = useLoad("drafts/" + id, stamp);
  const [tab, T] = useState("write");
  return (
    <Load record={rec}>
      {(d) => (
        <>
          <a className="back" href="#drafts">
            <ArrowLeft size={14} /> 稿件库
          </a>
          <Header
            title={d.evidence.title}
            desc={
              "母稿 #" +
              id +
              " · " +
              (d.version ? "版本 " + d.version : "尚未起稿")
            }
          />
          <div className="tabs">
            {[
              ["write", "母稿编辑"],
              ["channels", "渠道稿件"],
              ["history", "修订与批注"],
            ].map(([k, n]) => (
              <button key={k} aria-pressed={tab === k} onClick={() => T(k)}>
                {n}
              </button>
            ))}
          </div>
          {tab === "write" ? (
            <Write key={id + "-" + d.version} d={d} />
          ) : tab === "channels" ? (
            <Channels d={d} />
          ) : (
            <HistoryPane d={d} />
          )}
        </>
      )}
    </Load>
  );
}
function Sample({ d, value, set }) {
  return (
    <Field label="参考已审核的同作者文章（可选）">
      <select value={value} onChange={(e) => set(Number(e.target.value))}>
        <option value={0}>仅使用当前素材</option>
        {d.samples.map((s) => (
          <option key={s.id} value={s.id}>
            {s.topic__title}
          </option>
        ))}
      </select>
    </Field>
  );
}
function Write({ d }) {
  const { reviewer, run } = useApp(),
    [body, B] = useState(d.body),
    [reason, R] = useState(""),
    [budget, V] = useState(1),
    [sample, S] = useState(0);
  return (
    <div className="columns writing">
      <section className="panel">
        <div className="section-head">
          <h2>
            <Feather size={18} /> 母稿正文
          </h2>
          <Pill>{d.approved ? "已审核" : "编辑中"}</Pill>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(
              () =>
                api("drafts/" + d.id + "/save", {
                  body,
                  reason,
                  base: d.version,
                }),
              "修订已保存",
            );
          }}
        >
          <Field label="正文">
            <textarea
              className="manuscript"
              value={body}
              onChange={(e) => B(e.target.value)}
              required
              maxLength={40000}
              placeholder="写下第一段，使用 [S编号] 标注事实出处。"
            />
          </Field>
          <Field label="本次改稿理由">
            <input
              required
              value={reason}
              onChange={(e) => R(e.target.value)}
              maxLength={500}
            />
          </Field>
          <div className="actions">
            <Btn>保存修订</Btn>
            {reviewer && (
              <Btn
                type="button"
                secondary
                disabled={
                  !d.version || body !== d.body || d.approved === d.version
                }
                onClick={() =>
                  run(
                    () =>
                      api("drafts/" + d.id + "/approve", { base: d.version }),
                    "母稿审核通过",
                  )
                }
              >
                审核母稿
              </Btn>
            )}
          </div>
        </form>
        <details className="inset">
          <summary>用模型起稿或按批注改写</summary>
          <Sample d={d} value={sample} set={S} />
          <Field label="本次最多调用模型">
            <select value={budget} onChange={(e) => V(Number(e.target.value))}>
              <option value="1">1 次</option>
              <option value="2">2 次（校验失败后允许修订一次）</option>
            </select>
          </Field>
          <Btn
            secondary
            disabled={body !== d.body}
            onClick={() => {
              if (
                confirm(
                  "将把本选题证据、原话和已保存母稿发往配置的模型，最多 " +
                    budget +
                    " 次调用。确认？",
                )
              )
                run(
                  () =>
                    api("drafts/" + d.id + "/generate", {
                      base: d.version,
                      budget,
                      sample,
                      consent: true,
                    }),
                  "任务已登记，请查看运行记录",
                );
            }}
          >
            授权并提交任务
          </Btn>
        </details>
        {d.jobs.map((j) => (
          <p className="meta" key={j.id}>
            <a href="#runs">
              任务 #{j.id} · {stateNames[j.state]}
            </a>{" "}
            {j.detail}
          </p>
        ))}
      </section>
      <section className="panel references">
        <h2>写作依据</h2>
        <small>已确认的作者原话</small>
        <blockquote>{d.evidence.quote}</blockquote>
        <p className="meta">
          {d.evidence.author} · {d.evidence.locator}
        </p>
        <hr />
        <h3>
          <Link2 size={15} /> 选题来源
        </h3>
        {d.evidence.sources.map((s) => (
          <article key={s.id}>
            <Pill>S{s.id}</Pill>
            <h4>
              <Link href={s.url}>{s.title}</Link>
            </h4>
            <p>{s.excerpt}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
function HistoryPane({ d }) {
  const { run } = useApp(),
    [old, O] = useState(null);
  return (
    <div className="columns">
      <section className="panel">
        <h2>
          <History size={18} /> 修订历史
        </h2>
        {d.revisions.map((r) => (
          <div className="item" key={r.id}>
            <small>
              v{r.version} · {r.actor}
            </small>
            <p>{r.reason}</p>
            <div className="actions">
              <Btn
                secondary
                onClick={() =>
                  run(async () =>
                    O(await api("drafts/" + d.id + "/versions/" + r.version)),
                  )
                }
              >
                查看正文
              </Btn>
              {r.version !== d.version && (
                <Btn
                  secondary
                  onClick={() =>
                    run(
                      () =>
                        api("drafts/" + d.id + "/restore", {
                          base: d.version,
                          version: r.version,
                        }),
                      "历史正文已恢复为新版本",
                    )
                  }
                >
                  恢复此版
                </Btn>
              )}
            </div>
          </div>
        ))}
        {old && <pre className="prose">{old.body}</pre>}
      </section>
      <section className="panel">
        <h2>批注</h2>
        <form
          onSubmit={(e) => {
            const f = e.currentTarget,
              x = dataOf(e);
            run(async () => {
              await api("drafts/" + d.id + "/notes", {
                ...x,
                version: d.version,
              });
              f.reset();
            }, "批注已保存");
          }}
        >
          <Field label="引用的原句（可选）">
            <input name="anchor" maxLength={500} />
          </Field>
          <Field label="批注意见">
            <textarea name="text" required maxLength={1500} />
          </Field>
          <Btn disabled={!d.version}>添加批注</Btn>
        </form>
        {d.notes.map((n, i) => (
          <div key={i} className="item">
            <small>
              {n.actor} · v{n.revision__version}
            </small>
            {n.anchor && <blockquote>{n.anchor}</blockquote>}
            <p>{n.text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
function Channels({ d }) {
  const { run, stamp } = useApp(),
    [key, K] = useState("wechat"),
    record = useLoad("drafts/" + d.id + "/editions", stamp);
  return (
    <section className="panel">
      <div className="section-head">
        <h2>平台版本</h2>
        <Pill>母稿 v{d.version}</Pill>
      </div>
      <div className="channel-tabs">
        {Object.entries(platformNames).map(([k, n]) => (
          <button aria-pressed={key === k} key={k} onClick={() => K(k)}>
            {n}
          </button>
        ))}
      </div>
      <Load record={record}>
        {(rows) => {
          const ed = rows.find(
            (e) => e.platform === key && e.revision__version === d.version,
          );
          return ed && d.approved ? (
            <Edition key={ed.id + "-" + ed.version} ed={ed} d={d} />
          ) : (
            <Empty title={d.approved ? "待生成渠道稿" : "母稿需要先审核"}>
              {rows.some((e) => e.platform === key) ? "旧渠道稿已归档。 " : ""}
              <Btn
                disabled={!d.approved}
                onClick={() =>
                  run(
                    () =>
                      api("drafts/" + d.id + "/compile", {
                        base: d.version,
                        platform: key,
                      }),
                    "渠道稿已生成",
                  )
                }
              >
                从审核版生成
              </Btn>
            </Empty>
          );
        }}
      </Load>
    </section>
  );
}
function Edition({ ed, d }) {
  const { run, reviewer } = useApp(),
    [title, T] = useState(ed.title),
    [body, B] = useState(ed.body),
    [cards, C] = useState(ed.cards.join("\n---\n")),
    [out, O] = useState(""),
    [sample, S] = useState(0);
  const path = "editions/" + ed.id + "/",
    version = ed.version,
    dirty =
      title !== ed.title ||
      body !== ed.body ||
      cards !== ed.cards.join("\n---\n");
  return (
    <div className="channel-edit">
      <p className="meta">
        渠道 v{version} · {ed.approved ? "已审核" : "待审核"}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(
            () =>
              api(path + "save", {
                version,
                title,
                body,
                cards: cards.split("\n---\n"),
              }),
            "渠道修订已保存",
          );
        }}
      >
        <Field label="渠道标题">
          <input
            required
            value={title}
            onChange={(e) => T(e.target.value)}
            maxLength={ed.platform === "xhs" ? 20 : 300}
          />
        </Field>
        <Field label="渠道正文">
          <textarea
            required
            value={body}
            onChange={(e) => B(e.target.value)}
            rows={12}
          />
        </Field>
        {ed.platform === "xhs" && (
          <Field label="图卡文字（单独一行 --- 分卡）">
            <textarea
              value={cards}
              onChange={(e) => C(e.target.value)}
              rows={6}
            />
          </Field>
        )}
        <div className="actions">
          <Btn disabled={!dirty}>保存渠道修改</Btn>
          {reviewer && (
            <Btn
              secondary
              type="button"
              disabled={dirty || ed.approved}
              onClick={() =>
                run(() => api(path + "approve", { version }), "渠道稿审核通过")
              }
            >
              审核渠道稿
            </Btn>
          )}
        </div>
      </form>
      <details className="inset">
        <summary>按平台风格用模型改写</summary>
        <Sample d={d} value={sample} set={S} />
        <Btn
          secondary
          disabled={dirty}
          onClick={() => {
            if (
              confirm(
                "向已配置的模型发送本文素材及所选样本，最多调用两次。确认？",
              )
            )
              run(
                () =>
                  api(path + "generate", {
                    base: d.version,
                    version,
                    budget: 2,
                    sample,
                    consent: true,
                  }),
                "渠道改写任务已登记",
              );
          }}
        >
          授权渠道改写
        </Btn>
      </details>
      {reviewer && (
        <div className="actions inset">
          <Btn
            secondary
            disabled={!ed.approved || dirty}
            onClick={() =>
              run(
                () => api(path + "download", { version }, true),
                "文件已生成",
                false,
              )
            }
          >
            导出{ed.platform === "xhs" ? "图文包" : "文件"}
          </Btn>
          {["wechat", "x"].includes(ed.platform) && (
            <Btn
              disabled={!ed.approved || dirty}
              onClick={() => {
                if (
                  confirm(
                    "向 " +
                      platformNames[ed.platform] +
                      " 创建此版本的独立远端草稿？平台可能计费。",
                  )
                )
                  run(async () => {
                    const r = await api(path + "deliver", {
                      version,
                      consent: true,
                    });
                    O(stateNames[r.state] + " " + (r.remote_id || r.detail));
                  });
              }}
            >
              创建远端草稿
            </Btn>
          )}
        </div>
      )}
      {out && <p role="status">{out}</p>}
    </div>
  );
}
