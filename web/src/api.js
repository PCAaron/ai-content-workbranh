let csrf = "";
export async function api(path, body, file = false) {
  const opts =
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(body),
        };
  const response = await fetch("/api/" + path, {
    ...opts,
    credentials: "same-origin",
  });
  if (!response.ok) {
    if (response.status === 401 && path !== "login")
      window.dispatchEvent(new Event("signed-out"));
    let message = "操作失败 (" + response.status + ")";
    try {
      message = (await response.json()).error || message;
    } catch {
      if (response.status === 403) message = "会话验证已过期，请刷新重试";
    }
    throw new Error(message);
  }
  if (file) {
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download =
      response.headers
        .get("Content-Disposition")
        ?.match(/filename="([^"]+)"/)?.[1] || "download";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    return {};
  }
  const data = await response.json();
  if (data?.csrf) csrf = data.csrf;
  return data;
}
export const platformNames = {
  wechat: "微信公众号",
  x: "X 长文",
  xhs: "小红书",
  zsxq: "知识星球",
};
export const stateNames = {
  queued: "等待执行",
  running: "生成中",
  unknown: "待人工核对",
  conflict: "版本冲突",
  done: "已完成",
  failed: "失败",
  candidate: "候选",
  evaluated: "已评测",
  adopted: "已采纳",
  rolled_back: "已回退",
  sent: "已建远端草稿",
  absent: "已核实未送达",
  sending: "发送中",
  calling: "调用中",
  valid: "通过",
  invalid: "未达标",
};
