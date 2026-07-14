import smtplib
import os
from dotenv import load_dotenv

load_dotenv()


email = os.getenv("MY_EMAIL")
password = os.getenv("APP_PASSWORD")


print("Email:", email)
print("Password length:", len(password))


try:

    server = smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465
    )

    server.login(
        email,
        password
    )

    print("Gmail login successful ✅")

    server.quit()


except Exception as e:

    print("Gmail login failed ❌")
    print(e)