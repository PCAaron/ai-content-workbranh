import React, { useState } from "react";
import { Plus, Quote as QuoteIcon, Search } from "lucide-react";
import { api } from "./api";
import {
  Header,
  Btn,
  Field,
  Empty,
  useApp,
  useLoad,
  Load,
  go,
  dataOf,
  Pill,
  Link,
} from "./ui";

export function Library() {
  const { stamp } = useApp(),
    [tab, T] = useState("sources"),
    [text, S] = useState(""),
    [q, Q] = useState(""),
    [before, B] = useState(0);
  const record = useLoad(
    "library?q=" + encodeURIComponent(q) + (before ? "&before=" + before : ""),
    stamp,
  );
  return (
    <>
      <Header
        title="素材与选题"
        desc="外部报道提供事实背景，本人的原话决定写作角度。"
      />
      <div className="tabs">
        {[
          ["sources", "来源材料"],
          ["quotes", "本人原话"],
          ["topics", "选题池"],
        ].map(([key, label]) => (
          <button
            key={key}
            aria-pressed={tab === key}
            onClick={() => {
              T(key);
              B(0);
              Q("");
              S("");
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <Load record={record}>
        {(d) => (
          <>
            <div className="columns">
              <section className="panel">
                <form
                  className="search"
                  onSubmit={(e) => {
                    e.preventDefault();
                    Q(text);
                    B(0);
                  }}
                >
                  <Search size={17} />
                  <input
                    aria-label="搜索材料或标题"
                    value={text}
                    onChange={(e) => S(e.target.value)}
                    placeholder="搜索材料或标题"
                  />
                  <button>搜索</button>
                </form>
                {!d[tab].length ? (
                  <Empty title="暂无匹配记录" />
                ) : (
                  d[tab].map((x) => (
                    <article className="item" key={x.id}>
                      {tab === "sources" ? (
                        <>
                          <div className="meta">
                            <Pill>{x.origin}</Pill> S{x.id} ·{" "}
                            {x.byline || "署名未填"}
                          </div>
                          <h3>
                            <Link href={x.url}>{x.title}</Link>
                          </h3>
                          <p>{x.excerpt || "待补录节选"}</p>
                        </>
                      ) : tab === "quotes" ? (
                        <>
                          <QuoteIcon size={17} />
                          <blockquote>{x.text}</blockquote>
                          <small>
                            {x.author} · {x.locator}
                          </small>
                        </>
                      ) : (
                        <Topic item={x} />
                      )}
                    </article>
                  ))
                )}
                <div className="actions">
                  {before > 0 && <button onClick={() => B(0)}>返回最新</button>}
                  {d[tab].length === 60 && (
                    <button onClick={() => B(d[tab].at(-1).id)}>
                      更早记录
                    </button>
                  )}
                </div>
              </section>
              <section className="panel">
                <Form key={tab} tab={tab} entries={d} />
              </section>
            </div>
          </>
        )}
      </Load>
    </>
  );
}
function Topic({ item }) {
  const { run } = useApp();
  return (
    <>
      <small>已确认 · {item.sources.length} 条证据</small>
      <h3>{item.title}</h3>
      <Btn
        secondary
        onClick={() =>
          run(async () =>
            go("draft/" + (await api("drafts/open", { topic: item.id })).id),
          )
        }
      >
        打开母稿
      </Btn>
    </>
  );
}
function Form({ tab, entries }) {
  const { run, user } = useApp();
  const list = useLoad("library");
  const [feed, F] = useState("");
  const [pull, P] = useState("");
  const submit = (e) => {
    const form = e.currentTarget,
      d = dataOf(e);
    if (tab === "quotes") d.confirmed = Boolean(d.confirmed);
    if (tab === "topics") {
      d.sources = new FormData(form).getAll("sources").map(Number);
      d.quote = Number(d.quote);
      d.confirmed = Boolean(d.confirmed);
    }
    run(async () => {
      await api(tab, d);
      form.reset();
    }, "记录已保存");
  };
  return (
    <>
      <h2>
        {tab === "sources"
          ? "收集来源"
          : tab === "quotes"
            ? "记录本人原话"
            : "确认新选题"}
      </h2>
      <form onSubmit={submit}>
        {tab === "sources" ? (
          <>
            <Field label="来源类型">
              <select name="origin">
                <option>微信公众号</option>
                <option>X</option>
                <option>RSS</option>
                <option>其他</option>
              </select>
            </Field>
            <Field label="材料标题">
              <input name="title" required maxLength={300} />
            </Field>
            <Field label="原文链接">
              <input name="url" type="url" required placeholder="https://" />
            </Field>
            <Field label="原文署名">
              <input name="byline" maxLength={150} />
            </Field>
            <Field label="原文节选">
              <textarea name="excerpt" rows={4} maxLength={12000} />
            </Field>
            <details>
              <summary>原文时间（可选）</summary>
              <Field label="带时区的时间">
                <input
                  name="published"
                  placeholder="2026-11-20T09:00:00+08:00"
                />
              </Field>
            </details>
          </>
        ) : tab === "quotes" ? (
          <>
            <Field label="本人原话">
              <textarea name="text" required rows={5} />
            </Field>
            <Field label="出处或定位">
              <input
                name="locator"
                required
                placeholder="例如：编辑手记，第 3 段"
              />
            </Field>
            <label className="check">
              <input type="checkbox" name="confirmed" required />
              我确认这是我的原话，并授权用于写作
            </label>
          </>
        ) : (
          <>
            <Field label="选题标题">
              <input name="title" required />
            </Field>
            <Field label="引用本人原话">
              <select name="quote" required defaultValue="">
                <option value="" disabled>
                  请选择
                </option>
                {(list.data?.quotes || entries.quotes)
                  .filter((x) => x.author === user.user)
                  .map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.text.slice(0, 80)}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="关联来源（可多选）">
              <select name="sources" multiple required size={5}>
                {(list.data?.sources || entries.sources)
                  .filter((x) => x.excerpt)
                  .map((x) => (
                    <option key={x.id} value={x.id}>
                      S{x.id} · {x.title}
                    </option>
                  ))}
              </select>
            </Field>
            <label className="check">
              <input type="checkbox" name="confirmed" required />
              我已核对观点归属及选题角度
            </label>
          </>
        )}
        <Btn>
          <Plus size={15} />
          {tab === "topics" ? "确认选题" : "保存记录"}
        </Btn>
      </form>
      {tab === "sources" && entries.feeds.length > 0 && (
        <div className="inset">
          <h3>拉取订阅</h3>
          <Field label="已配置的信源">
            <select value={feed} onChange={(e) => F(e.target.value)}>
              <option value="">请选择</option>
              {entries.feeds.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </Field>
          <Btn
            disabled={!feed}
            onClick={() =>
              run(async () => {
                const r = await api("pull", { name: feed });
                P(
                  "本轮新增 " +
                    r.added +
                    " 条" +
                    (r.more ? "，可继续拉取下一页" : ""),
                );
              })
            }
          >
            拉取一页
          </Btn>
          <p>{pull}</p>
        </div>
      )}
    </>
  );
}
