import html
import io
import json
import os
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

from .http import Problem

PLATFORMS = {"wechat": "公众号", "x": "X 长文", "xhs": "小红书", "zsxq": "知识星球"}


def sections(body):
    return [line.strip() for line in body.splitlines() if line.strip()]


def adapt(rev, platform):
    topic = rev.draft.topic
    paragraphs = sections(rev.body)
    quote = topic.quote.text
    title = topic.title
    if platform == "xhs":
        highlights = [re.sub(r"\[S\d+\]", "", p).strip() for p in paragraphs]
        cards = [title[:80]] + [s[:150] for s in highlights[:5] if s]
        body = "\n\n".join(paragraphs)[:1000]
        return dict(title=title[:20], body=body, cards=cards)
    if platform == "x":
        body = quote + "\n\n" + "\n\n".join(p for p in paragraphs if p != quote)
    elif platform == "zsxq":
        body = rev.body + "\n\n讨论问题：" + topic.title
    else:
        body = rev.body
    return dict(title=title, body=body, cards=[])


def article_html(title, body):
    return (
        "<article><h1>"
        + html.escape(title)
        + "</h1>"
        + "".join("<p>" + html.escape(p) + "</p>" for p in sections(body))
        + "</article>"
    )


def sources_text(edition):
    return "\n".join(
        f"[S{s.pk}] {s.title} · {s.url}"
        for s in edition.revision.draft.topic.sources.order_by("pk")
    )


def card_png(content, index, count):
    path = os.getenv(
        "PRESS_CJK_FONT", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    )
    if not Path(path).is_file():
        raise Problem("图卡需要中文字体文件，请配置 PRESS_CJK_FONT", 503)
    canvas = Image.new("RGB", (1080, 1440), "#f4f1e8" if index else "#203c33")
    draw = ImageDraw.Draw(canvas)
    ink = "#233e35" if index else "#faf6e9"

    def font(size):
        return ImageFont.truetype(path, size)

    draw.rectangle((82, 96, 165, 106), fill="#c66e48")
    draw.text((82, 150), "编辑手记" if index else "本期观点", font=font(38), fill=ink)
    # Measure actual glyph widths. Long paragraphs wrap; unsupported length fails explicitly.
    for size in (72, 60, 52, 44):
        face = font(size)
        lines = []
        for para in content.splitlines():
            line = ""
            for char in para:
                if line and face.getlength(line + char) > 905:
                    lines.append(line)
                    line = ""
                line += char
            lines.append(line)
        if len(lines) * (size + 23) <= 960:
            break
    else:
        raise Problem("图卡文字超出版面，请拆成两张卡")
    for i, line in enumerate(lines):
        draw.text((82, 270 + i * (size + 23)), line, font=face, fill=ink)
    draw.line((82, 1280, 998, 1280), fill=ink, width=2)
    draw.text((82, 1310), f"{index + 1:02d} / {count:02d}", font=font(32), fill=ink)
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def render(edition):
    refs = sources_text(edition)
    body = edition.body + "\n\n来源\n" + refs
    if edition.platform == "wechat":
        return (
            "html",
            "text/html; charset=utf-8",
            (
                "<!doctype html><meta charset=utf-8>"
                + article_html(edition.title, body)
            ).encode(),
        )
    if edition.platform == "xhs":
        data = io.BytesIO()
        with ZipFile(data, "w", ZIP_DEFLATED) as archive:
            archive.writestr("caption.txt", edition.title + "\n\n" + edition.body)
            archive.writestr("sources.txt", refs)
            archive.writestr(
                "cards.json", json.dumps(edition.cards, ensure_ascii=False, indent=2)
            )
            for i, card in enumerate(edition.cards):
                archive.writestr(
                    f"{i + 1:02d}.png", card_png(card, i, len(edition.cards))
                )
        return "zip", "application/zip", data.getvalue()
    markdown = edition.platform == "zsxq"
    return (
        ("md" if markdown else "txt"),
        "text/plain; charset=utf-8",
        (("# " if markdown else "") + edition.title + "\n\n" + body).encode(),
    )
