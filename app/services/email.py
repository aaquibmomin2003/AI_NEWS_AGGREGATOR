import os
import smtplib
import html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
import markdown


load_dotenv()


MY_EMAIL = os.getenv("MY_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")


if APP_PASSWORD:
    APP_PASSWORD = APP_PASSWORD.strip()



# -----------------------------------
# Send Email
# -----------------------------------

def send_email(
        subject: str,
        body_text: str,
        body_html: str = None,
        recipients: list = None
):

    if not MY_EMAIL:
        raise ValueError(
            "MY_EMAIL environment variable is not set"
        )

    if not APP_PASSWORD:
        raise ValueError(
            "APP_PASSWORD environment variable is not set"
        )


    if recipients is None:
        recipients = [MY_EMAIL]


    recipients = [
        email for email in recipients
        if email
    ]


    if not recipients:
        raise ValueError(
            "No valid recipients provided"
        )



    msg = MIMEMultipart("alternative")

    msg["Subject"] = subject
    msg["From"] = MY_EMAIL
    msg["To"] = ", ".join(recipients)



    # Plain text
    msg.attach(
        MIMEText(
            body_text,
            "plain"
        )
    )


    # HTML
    if body_html:

        msg.attach(
            MIMEText(
                body_html,
                "html"
            )
        )



    try:

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as smtp:


            smtp.login(
                MY_EMAIL,
                APP_PASSWORD
            )


            smtp.sendmail(
                MY_EMAIL,
                recipients,
                msg.as_string()
            )


        print(
            "Email sent successfully ✅"
        )


    except smtplib.SMTPAuthenticationError as e:

        print(
            """
Gmail Authentication Failed ❌

Check:
1. Enable 2-Step Verification
2. Create Gmail App Password
3. Put App Password in .env
4. Remove spaces from App Password
"""
        )

        raise e




# -----------------------------------
# Markdown -> HTML
# -----------------------------------

def markdown_to_html(
        markdown_text: str
) -> str:


    html_content = markdown.markdown(
        markdown_text,
        extensions=[
            "extra",
            "nl2br"
        ]
    )


    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="utf-8">

<style>

body {{

font-family:
Arial,
Helvetica,
sans-serif;

line-height:1.6;

color:#333;

max-width:600px;

margin:auto;

padding:20px;

}}


h2,h3 {{

color:#222;

}}


a {{

color:#0066cc;

text-decoration:none;

}}


hr {{

border:none;

border-top:1px solid #ddd;

margin:20px 0;

}}

</style>

</head>


<body>

{html_content}

</body>


</html>
"""





# -----------------------------------
# Digest Response HTML
# -----------------------------------

def digest_to_html(
        digest_response
):

    from app.agent.email_agent import EmailDigestResponse



    if not isinstance(
        digest_response,
        EmailDigestResponse
    ):

        if hasattr(
            digest_response,
            "to_markdown"
        ):

            return markdown_to_html(
                digest_response.to_markdown()
            )


        return markdown_to_html(
            str(digest_response)
        )



    html_parts = []



    # Greeting

    greeting = markdown.markdown(
        digest_response.introduction.greeting
    )


    html_parts.append(
        f"""
        <h3>{greeting}</h3>
        """
    )



    # Introduction

    intro = markdown.markdown(
        digest_response.introduction.introduction
    )


    html_parts.append(
        f"""
        <p>{intro}</p>
        """
    )



    html_parts.append(
        "<hr>"
    )



    # Articles

    for article in digest_response.articles:


        title = html.escape(
            article.title
        )


        summary = markdown.markdown(
            article.summary,
            extensions=[
                "extra",
                "nl2br"
            ]
        )


        url = html.escape(
            article.url
        )



        html_parts.append(
            f"""
<h3>{title}</h3>

<p>
{summary}
</p>

<p>
<a href="{url}">
Read more →
</a>
</p>

<hr>

"""
        )



    html_content = "\n".join(
        html_parts
    )



    return f"""

<!DOCTYPE html>

<html>

<head>

<meta charset="utf-8">


<style>

body {{

font-family:
Arial,
Helvetica,
sans-serif;

line-height:1.6;

color:#333;

max-width:600px;

margin:auto;

padding:20px;

}}


h3 {{

color:#222;

}}


a {{

color:#0066cc;

text-decoration:none;

}}


hr {{

border:none;

border-top:1px solid #ddd;

margin:20px 0;

}}

</style>


</head>


<body>


{html_content}


</body>


</html>

"""





# -----------------------------------
# Send Digest To Self
# -----------------------------------

def send_email_to_self(
        subject: str,
        body: str
):

    if not MY_EMAIL:

        raise ValueError(
            "MY_EMAIL missing in .env"
        )


    send_email(
        subject,
        body,
        recipients=[
            MY_EMAIL
        ]
    )




# -----------------------------------
# Test
# -----------------------------------

if __name__ == "__main__":


    send_email_to_self(
        "Test from AI News Aggregator",
        "Hello! Gmail SMTP is working 🚀"
    )