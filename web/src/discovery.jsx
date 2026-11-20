import React, { useState } from "react";
import { Search } from "lucide-react";
import { api } from "./api";
import { Btn, Empty, Field, Link, useApp } from "./ui";

const names = { x: "X 公开帖", wechat: "微信公众号" };
const metricNames = {
  like_count: "赞",
  retweet_count: "转发",
  reply_count: "回复",
  quote_count: "引用",
};

export function Discovery() {
  const { busy, run } = useApp();
  const [platform, setPlatform] = useState("x");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [result, setResult] = useState(null);
  function submit(event) {
    event.preventDefault();
    run(
      async () => {
        setResult(null);
        setResult(
          await api("discovery/search", {
            platform,
            query,
            limit,
            request_id: crypto.randomUUID(),
          }),
        );
      },
      "",
      false,
    );
  }
  return (
    <div className="columns discovery">
      <section className="panel">
        <h2>按主题找素材</h2>
        <form onSubmit={submit}>
          <Field label="检索平台">
            <select
              value={platform}
              disabled={busy}
              onChange={(e) => {
                setPlatform(e.target.value);
                setLimit(10);
                setResult(null);
              }}
            >
              {Object.entries(names).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="主题词">
            <input
              value={query}
              maxLength={120}
              required
              disabled={busy}
              placeholder="例如：DeepSeek 推理"
              onChange={(e) => setQuery(e.target.value)}
            />
          </Field>
          <Field label="本次样本上限">
            <select
              value={limit}
              disabled={busy}
              onChange={(e) => setLimit(Number(e.target.value))}
            >
              {(platform === "x" ? [10, 20, 50] : [10, 20]).map((n) => (
                <option key={n} value={n}>
                  {n} 条
                </option>
              ))}
            </select>
          </Field>
          <p className="muted">
            {platform === "x"
              ? "检索最近七天公开帖，按最新取样，过滤纯转发。"
              : "按搜索索引的近一周筛选公开公众号文章，覆盖范围取决于收录情况。"}
            每次检索使用一次服务请求。
          </p>
          <Btn>
            <Search size={16} />
            检索主题
          </Btn>
        </form>
      </section>
      <section className="panel" aria-live="polite">
        {result ? (
          <Results result={result} />
        ) : (
          <Empty title={busy ? "正在检索…" : "输入主题查看样本"} />
        )}
      </section>
    </div>
  );
}

function Results({ result }) {
  const { rows, summary, platform } = result;
  return (
    <>
      <h2>
        {names[platform]} · {result.query}
      </h2>
      <p className="muted">
        采样于 {new Date(result.observed).toLocaleString()} · 上限{" "}
        {result.limit} 条
      </p>
      <div className="inset">
        <b>去重样本 {summary.count} 条</b>
        {platform === "x" ? (
          <>
            <p>
              可识别作者 {summary.authors} 位 · 具备四项互动数据{" "}
              {summary.measured}/{summary.count} 条
            </p>
            <p>
              单帖互动中位数 {summary.median ?? "暂无数据"} ·
              互动合计为赞、转发、回复及引用之和
            </p>
          </>
        ) : (
          <p>
            有索引摘要 {summary.with_preview}/{summary.count} 篇 ·
            阅读量和点赞数未知
          </p>
        )}
        <p>
          可见文本命中篇数 ·{" "}
          {Object.entries(summary.mentions)
            .map(([t, n]) => t + " " + n)
            .join(" / ")}
        </p>
      </div>
      {rows.length === 0 && <Empty title="本次检索未取得匹配样本" />}
      {rows.map((row) => (
        <Candidate key={row.ticket} row={row} platform={platform} />
      ))}
    </>
  );
}

function Candidate({ row, platform }) {
  const { run } = useApp();
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(null);
  const [title, setTitle] = useState("");
  const [excerpt, setExcerpt] = useState("");
  function capture() {
    run(async () => {
      setSaved(
        await api("discovery/capture", { ticket: row.ticket, title, excerpt }),
      );
      setEditing(false);
    }, "已核对来源库");
  }
  return (
    <article className="item">
      <h3>
        <Link href={row.url}>{row.title}</Link>
      </h3>
      {platform === "x" && (
        <small>
          {row.byline ? "@" + row.byline : "署名未知"}
          {row.published && " · " + new Date(row.published).toLocaleString()}
        </small>
      )}
      {row.preview && (platform !== "x" || row.preview !== row.title) && (
        <p>{row.preview}</p>
      )}
      {platform === "x" && (
        <p className="meta">
          {Object.entries(metricNames)
            .map(([k, label]) => label + " " + (row.metrics[k] ?? "未知"))
            .join(" · ")}
        </p>
      )}
      {saved ? (
        <small>
          {saved.created ? "已加入来源材料" : "来源库已有此材料"} · S{saved.id}
        </small>
      ) : editing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            capture();
          }}
        >
          <Field label="核对后的原文标题">
            <input
              required
              maxLength={300}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>
          <Field label="原文节选（可稍后补录）">
            <textarea
              maxLength={12000}
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
            />
          </Field>
          <div className="actions">
            <Btn>保存核对结果</Btn>
            <Btn type="button" secondary onClick={() => setEditing(false)}>
              取消
            </Btn>
          </div>
        </form>
      ) : (
        <Btn
          secondary
          onClick={platform === "x" ? capture : () => setEditing(true)}
        >
          {platform === "x" ? "加入来源材料" : "核对原文并入库"}
        </Btn>
      )}
    </article>
  );
}
