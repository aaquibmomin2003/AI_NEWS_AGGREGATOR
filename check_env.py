import os
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("MY_EMAIL")
password = os.getenv("APP_PASSWORD")


print("EMAIL:", email)
print("PASSWORD:", password)
print("PASSWORD LENGTH:", len(password) if password else None)