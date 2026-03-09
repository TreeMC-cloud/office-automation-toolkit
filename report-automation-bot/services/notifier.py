    from __future__ import annotations

    import json
    import smtplib
    import ssl
    import urllib.request
    from email.message import EmailMessage


    def build_notification_text(summary_text: str, overview: dict[str, object]) -> str:
        return (
            f"自动报表通知
"
            f"最新周期：{overview.get('latest_period')}
"
            f"总记录数：{overview.get('total_records')}
"
            f"总指标值：{overview.get('total_value')}

"
            f"摘要：
{summary_text}"
        )


    def send_feishu(webhook_url: str, text: str) -> str:
        payload = json.dumps({"msg_type": "text", "content": {"text": text}}).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8")


    def send_email(
        smtp_server: str,
        smtp_port: int,
        sender: str,
        password: str,
        recipients: list[str],
        subject: str,
        html_body: str,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content("请使用支持 HTML 的邮件客户端查看完整内容。")
        message.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender, password)
            server.send_message(message)
