"""通知发送 — 飞书卡片/邮件附件/STARTTLS/重试"""

from __future__ import annotations

import json
import smtplib
import ssl
import time
import urllib.request
from email import encoders
from email.message import EmailMessage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def build_notification_text(summary_text: str, overview: dict) -> str:
    return (
        f"📬 自动报表通知\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"最新周期：{overview.get('latest_period')}\n"
        f"总记录数：{overview.get('total_records'):,}\n"
        f"总指标值：{overview.get('total_value'):,.2f}\n"
        f"均值：{overview.get('average_value'):,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{summary_text}"
    )


def send_feishu(webhook_url: str, text: str, overview: dict | None = None, max_retries: int = 3) -> str:
    """
    飞书 Webhook 推送。
    如果提供 overview，发送卡片消息；否则发送纯文本。
    """
    if overview:
        payload = _build_feishu_card(text, overview)
    else:
        payload = {"msg_type": "text", "content": {"text": text}}

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                webhook_url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                code = result.get("code", result.get("StatusCode", 0))
                if code != 0:
                    raise RuntimeError(f"飞书返回错误：code={code}, msg={result.get('msg', '')}")
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def _build_feishu_card(text: str, overview: dict) -> dict:
    """构建飞书卡片消息"""
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📊 自动报表通知"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**总记录数**\n{overview.get('total_records', 0):,}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**总指标值**\n{overview.get('total_value', 0):,.2f}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**均值**\n{overview.get('average_value', 0):,.2f}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**最新周期**\n{overview.get('latest_period', '-')}"}},
                    ],
                },
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "plain_text", "content": text[:500]}},
            ],
        },
    }


def send_dingtalk(webhook_url: str, text: str, overview: dict | None = None, max_retries: int = 3) -> str:
    """钉钉 Webhook 推送。有 overview 时用 markdown 消息，否则纯文本。"""
    if overview:
        md_text = (
            f"## 📊 自动报表通知\n\n"
            f"- 最新周期：{overview.get('latest_period', '-')}\n"
            f"- 总记录数：{overview.get('total_records', 0):,}\n"
            f"- 总指标值：{overview.get('total_value', 0):,.2f}\n"
            f"- 均值：{overview.get('average_value', 0):,.2f}\n\n"
            f"{text[:2000]}"
        )
        payload = {"msgtype": "markdown", "markdown": {"title": "自动报表", "text": md_text}}
    else:
        payload = {"msgtype": "text", "text": {"content": text}}

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                webhook_url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("errcode", 0) != 0:
                    raise RuntimeError(f"钉钉返回错误：{result.get('errmsg', '')}")
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def send_wechat_work(webhook_url: str, text: str, max_retries: int = 3) -> str:
    """企业微信 Webhook 推送"""
    payload = {"msgtype": "text", "text": {"content": text}}
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                webhook_url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("errcode", 0) != 0:
                    raise RuntimeError(f"企业微信返回错误：{result.get('errmsg', '')}")
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def send_email(
    smtp_server: str,
    smtp_port: int,
    sender: str,
    password: str,
    recipients: list[str],
    subject: str,
    html_body: str,
    attachment: bytes | None = None,
    attachment_name: str = "报表.xlsx",
    max_retries: int = 3,
) -> None:
    """发送邮件，支持 SSL(465) 和 STARTTLS(587)，可附带 Excel 附件"""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    # HTML 正文
    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    # 附件
    if attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment",
                        filename=("utf-8", "", attachment_name))
        msg.attach(part)

    for attempt in range(max_retries):
        try:
            if smtp_port == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_server, smtp_port, context=ctx) as server:
                    server.login(sender, password)
                    server.sendmail(sender, recipients, msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(sender, password)
                    server.sendmail(sender, recipients, msg.as_string())
            return
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
