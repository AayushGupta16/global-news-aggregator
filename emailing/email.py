import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

# Load environment variables from the project root
load_dotenv()

EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

subject = "here's the latest China press release"
sender = "aayugupta04@gmail.com"
recipients = ["aayugupta04@gmail.com", "Carter.anderson0404@gmail.com"]


def send_email(subject: str, body: str, sender: str, recipients: list, password: str):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())
    print("Message sent!")
