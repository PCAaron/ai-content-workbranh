import React, { useState } from "react";
import { api, stateNames, platformNames } from "./api";
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
} from "./ui";

export function Operations() {
  const { stamp, run, reviewer, refresh } = useApp(),
    [tab, setTab] = useState("jobs"),
    [receipt, setReceipt] = useState(null);
  const list = useLoad(tab, stamp);
  return (
    <>
      <Header title="运行记录" desc="核对生成任务、平台草稿回执及操作审计。">
        <button className="btn secondary" onClick={refresh}>
          刷新
        </button>
      </Header>
      <div className="tabs">
        {(reviewer
          ? [
              ["jobs", "模型任务"],
              ["deliveries", "平台回执"],
              ["audit", "操作审计"],
            ]
          : [["jobs", "模型任务"]]
        ).map(([k, n]) => (
          <button
            key={k}
            aria-pressed={tab === k}
            onClick={() => {
              setTab(k);
              setReceipt(null);
            }}
          >
            {n}
          </button>
        ))}
      </div>
      <section className="panel">
        <Load record={list}>
          {(rows) =>
            rows.length ? (
              rows.map((r) => (
                <article key={r.id} className="item">
                  {tab === "audit" ? (
                    <>
                      <b>{r.action}</b>
                      <p>
                        {r.actor} · {r.target} ·{" "}
                        {new Date(r.at).toLocaleString()}
                      </p>
                    </>
                  ) : tab === "jobs" ? (
                    <>
                      <div className="section-head">
                        <b>{r.draft__topic__title}</b>
                        <Pill>{stateNames[r.state]}</Pill>
                      </div>
                      <p>
                        #{r.id} · {r.model} · 最多 {r.budget} 次调用
                      </p>
                      <p>{r.detail}</p>
                      <Btn
                        secondary
                        onClick={() =>
                          run(async () => setReceipt(await api("jobs/" + r.id)))
                        }
                      >
                        查看回执
                      </Btn>
                    </>
                  ) : (
                    <>
                      <b>
                        {platformNames[r.edition__platform]} · v{r.version}
                      </b>{" "}
                      <Pill>{stateNames[r.state]}</Pill>
                      <p>{r.remote_id || r.detail}</p>
                      {["sending", "unknown"].includes(r.state) && (
                        <details>
                          <summary>人工对账</summary>
                          <form
                            onSubmit={(e) => {
                              const d = dataOf(e);
                              run(
                                () =>
                                  api("deliveries/" + r.id + "/reconcile", {
                                    ...d,
                                    found: !!d.remote_id,
                                  }),
                                "已记录对账结果",
                              );
                            }}
                          >
                            <Field label="平台草稿编号（确认不存在时留空）">
                              <input name="remote_id" />
                            </Field>
                            <Field label="核对依据">
                              <input name="reason" required />
                            </Field>
                            <Btn>提交核对结果</Btn>
                          </form>
                        </details>
                      )}
                    </>
                  )}
                </article>
              ))
            ) : (
              <Empty title="暂无记录" />
            )
          }
        </Load>
        {receipt && (
          <div className="inset">
            <h3>任务 #{receipt.id} 调用记录</h3>
            {receipt.attempts.map((a) => (
              <details key={a.sequence}>
                <summary>
                  第 {a.sequence} 次 · {stateNames[a.state]} {a.detail}
                </summary>
                <pre className="prose">{a.result || "尚无响应正文"}</pre>
              </details>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
export function Learning() {
  const { stamp } = useApp(),
    list = useLoad("learning", stamp);
  return (
    <>
      <Header
        title="文风实验室"
        desc="把真实改稿中的措辞变化，放到独立文章上验证。"
      />
      <Load record={list}>
        {(d) => (
          <div className="columns">
            <section className="panel">
              <h2>规则版本</h2>
              {d.rules.length ? (
                d.rules.map((r) => <Rule key={r.id} r={r} d={d} />)
              ) : (
                <Empty title="还没有文风规则">
                  先在稿件中保存两次有差异的修订，并记录修改理由。
                </Empty>
              )}
            </section>
            <section className="panel">
              <Candidate d={d} />
            </section>
          </div>
        )}
      </Load>
    </>
  );
}
function Candidate({ d }) {
  const { run } = useApp(),
    [id, setId] = useState(""),
    [old, setOld] = useState(""),
    [next, setNext] = useState(""),
    [sample, setSample] = useState(null);
  return (
    <>
      <h2>从改稿提取候选</h2>
      <Field label="训练修订">
        <select
          value={id}
          onChange={(e) => {
            setId(e.target.value);
            setSample(null);
            setOld("");
            setNext("");
          }}
        >
          <option value="">选择人工修订</option>
          {d.pairs.map((p) => (
            <option key={p.id} value={p.id}>
              {p.draft__topic__title} · v{p.version}
            </option>
          ))}
        </select>
      </Field>
      <Btn
        secondary
        disabled={!id}
        onClick={() =>
          run(async () => {
            const s = await api("learning/examples/" + id);
            setSample(s);
            setOld(s.options[0]?.old || "");
            setNext(s.options[0]?.new || "");
          })
        }
      >
        提取措辞差异
      </Btn>
      {sample && (
        <>
          <p className="meta">改稿理由 · {sample.reason}</p>
          <details>
            <summary>比对原文与改稿</summary>
            <pre className="prose">{sample.before}</pre>
            <hr />
            <pre className="prose">{sample.after}</pre>
          </details>
          <Field label="原措辞">
            <input value={old} onChange={(e) => setOld(e.target.value)} />
          </Field>
          <Field label="新措辞">
            <input value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
          <Btn
            disabled={!old || !next}
            onClick={() =>
              run(
                () => api("rules", { training: Number(id), old, new: next }),
                "候选规则已保存",
              )
            }
          >
            保存候选
          </Btn>
        </>
      )}
    </>
  );
}
function Rule({ r, d }) {
  const { run, reviewer } = useApp(),
    [ids, setIds] = useState([]);
  return (
    <div className="item">
      <div className="section-head">
        <b>
          「{r.old}」 → 「{r.new}」
        </b>
        <Pill>{d.active === r.id ? "当前生效" : stateNames[r.status]}</Pill>
      </div>
      <p>{r.reason}</p>
      {["candidate", "evaluated"].includes(r.status) && (
        <>
          <Field label="独立验证样本（可多选）">
            <select
              multiple
              value={ids}
              onChange={(e) =>
                setIds([...e.target.selectedOptions].map((o) => o.value))
              }
            >
              {d.pairs
                .filter((p) => p.id !== r.training_id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.draft__topic__title} · v{p.version}
                  </option>
                ))}
            </select>
          </Field>
          <Btn
            secondary
            disabled={!ids.length}
            onClick={() =>
              run(
                () =>
                  api("rules/" + r.id + "/evaluate", {
                    examples: ids.map(Number),
                  }),
                "评测已保存",
              )
            }
          >
            运行对照评测
          </Btn>
        </>
      )}
      {r.evaluation.map((s) => (
        <p className="meta" key={s.revision}>
          稿件 #{s.draft} · 基线 {s.baseline} → 候选 {s.candidate}
        </p>
      ))}
      {reviewer && r.status === "evaluated" && (
        <Btn
          onClick={() =>
            run(() => api("rules/" + r.id + "/activate", {}), "新规则已启用")
          }
        >
          批准启用
        </Btn>
      )}
      {reviewer && d.active === r.id && (
        <Btn
          secondary
          onClick={() =>
            run(
              () => api("rules/" + r.id + "/rollback", { epoch: d.epoch }),
              "已恢复上一版文风",
            )
          }
        >
          回滚此规则
        </Btn>
      )}
    </div>
  );
}
