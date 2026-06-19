import sys
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv


load_dotenv("/opt/notifier/notifier.env")


def main():
    if len(sys.argv) != 3:
        print("Usage: notifier.py <event> <service>", file=sys.stderr)
        sys.exit(1)

    event = sys.argv[1]
    service = sys.argv[2]
    subject = f"{service} = {event.upper()}"

    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("ALERT_TO")

    if not gmail_user or not gmail_pass or not recipient:
        print("Missing GMAIL_USER or GMAIL_APP_PASSWORD or ALERT_TO in .env", file=sys.stderr)
        sys.exit(2)

    msg = EmailMessage()
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content("")

    print(f"Created email with subject: {subject}")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(gmail_user, gmail_pass)
            smtp.send_message(msg)
        print(f"Notification sent correctly to {recipient} from {gmail_user}")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
