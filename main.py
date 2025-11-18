import os
import requests
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")


def fetch_physical_orders_last_month():
    """Fetch physical orders from the previous full calendar month."""

    today = datetime.utcnow()

    # First day of this month
    first_of_this_month = today.replace(day=1)

    # Last day of previous month
    last_of_prev_month = first_of_this_month - timedelta(days=1)

    # First day of previous month
    first_of_prev_month = last_of_prev_month.replace(day=1)

    # Format dates
    start_date = first_of_prev_month.strftime("%Y-%m-%dT00:00:00")
    end_date = last_of_prev_month.strftime("%Y-%m-%dT23:59:59")

    query = f"""
    query {{
      orders(first: 250, query: "created_at:>={start_date} AND created_at:<={end_date}") {{
        edges {{
          node {{
            name
            createdAt
            requiresShipping
            totalPriceSet {{
              shopMoney {{
                amount
                currencyCode
              }}
            }}
          }}
        }}
      }}
    }}
    """

    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-10/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json={"query": query})
    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise Exception(f"Shopify GraphQL errors: {data['errors']}")

    order_edges = data["data"]["orders"]["edges"]
    physical_orders = [edge["node"] for edge in order_edges if edge["node"]["requiresShipping"]]

    return physical_orders


def send_email_report(orders):
    prev_month = (datetime.utcnow().replace(day=1) - timedelta(days=1))
    month_name = prev_month.strftime("%B")
    year = prev_month.strftime("%Y")
    subject = f"Shopify Monthly Report – {month_name} {year} – {len(orders)} physical orders"

    if not orders:
        body = "No physical orders this month."
    else:
        lines = ["Physical orders this month:", ""]
        for o in orders:
            lines.append(
                f"- {o['name']} | {o['createdAt']} | {o['totalPriceSet']['shopMoney']['amount']} {o['totalPriceSet']['shopMoney']['currencyCode']}"
            )
        body = "\n".join(lines)

    message = Mail(
        from_email=EMAIL_FROM,
        to_emails=EMAIL_TO,
        subject=subject,
        plain_text_content=body,
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent successfully, status {response.status_code}.")
    except Exception as e:
        print("Email failed:", e)


if __name__ == "__main__":
    orders = fetch_physical_orders_last_month()
    print(f"Fetched {len(orders)} physical orders.")
    send_email_report(orders)