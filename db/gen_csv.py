"""Small-scale sample-data generator for the PostgreSQL port.

Reuses the UPSTREAM Snowflake lab's generator functions (config.py,
orders_generator, items_generator, reviews_generator, tickets_generator) at a
local-friendly scale and writes plain CSV (no pyarrow). generate.py itself is
NOT imported because it depends on pyarrow.

Point SEED_DIR at the lab's `seed_data_generator/` directory, e.g.:
  SEED_DIR=/path/to/sfguide-build-end-to-end-ai-app-on-snowflake/seed_data_generator \
      python db/gen_csv.py
(lab repo: https://github.com/Snowflake-Labs/sfguide-build-end-to-end-ai-app-on-snowflake)
"""
import csv
import os
import random
import sys
from datetime import datetime, timedelta

SEED_DIR = os.environ.get("SEED_DIR", "./seed_data_generator")
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, SEED_DIR)

# --- scale down BEFORE importing the generators that bind these at import time ---
import config
config.TOTAL_ORDERS = 50_000
config.NUM_CUSTOMERS = 10_000
config.NUM_REVIEWS = 1_200
config.NUM_TICKETS = 1_200

import orders_generator
import items_generator
import reviews_generator
import tickets_generator
# rebind the names the modules imported by value
orders_generator.TOTAL_ORDERS = config.TOTAL_ORDERS
reviews_generator.NUM_REVIEWS = config.NUM_REVIEWS
tickets_generator.NUM_TICKETS = config.NUM_TICKETS

SEED = 42
NUM_CUSTOMERS = config.NUM_CUSTOMERS


def generate_customers(num_customers):
    """Mirror of generate.py:generate_customers (inlined to avoid pyarrow import)."""
    random.seed(SEED)
    first_names = ["John", "Sarah", "Michael", "Emily", "David", "Jessica", "Chris", "Ashley",
                   "Matt", "Amanda", "Ryan", "Lauren", "Kevin", "Nicole", "Brian", "Rachel",
                   "Tyler", "Megan", "Josh", "Katie"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                  "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
                  "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    cities = ["Denver", "Salt Lake City", "Boulder", "Aspen", "Park City", "Jackson",
              "Telluride", "Steamboat Springs", "Vail", "Breckenridge", "Mammoth Lakes",
              "Tahoe City", "Whistler", "Banff", "Portland"]
    states = ["CO", "UT", "WY", "CA", "WA", "OR", "MT", "ID", "NV", "BC"]
    streets = ['Main St', 'Oak Ave', 'Maple Dr', 'Cedar Ln', 'Pine Rd', 'Elm St',
               'Washington Blvd', 'Lake View Dr', 'Mountain Way', 'Summit Trail']
    segments = ["Premium", "Standard", "Basic"]
    rows = []
    for i in range(1, num_customers + 1):
        reg_days_ago = random.randint(1, 1825)
        reg_date = (datetime(2026, 6, 4) - timedelta(days=reg_days_ago)).strftime("%Y-%m-%d")
        rows.append({
            "customer_id": i,
            "first_name": random.choice(first_names),
            "last_name": random.choice(last_names),
            "email": f"customer{i}@email.com",
            "phone": f"555-{random.randint(100,999):03d}-{random.randint(1000,9999):04d}",
            "address": f"{random.randint(100,9999)} {random.choice(streets)}",
            "city": random.choice(cities),
            "state": random.choice(states),
            "zip_code": f"{random.randint(10000,99999)}",
            "registration_date": reg_date,
            "customer_segment": random.choice(segments),
        })
    return rows


def write_csv(name, rows, fields):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  {name:28s} {len(rows):>8,} rows")
    return len(rows)


def main():
    random.seed(SEED)
    print(f"Generating sample data -> {OUT_DIR}")

    customers = generate_customers(NUM_CUSTOMERS)
    write_csv("customers.csv", customers, [
        "customer_id", "first_name", "last_name", "email", "phone", "address",
        "city", "state", "zip_code", "registration_date", "customer_segment"])

    customer_segments = {"Premium": [], "Standard": [], "Basic": []}
    for c in customers:
        customer_segments[c["customer_segment"]].append(c["customer_id"])
    customer_ids = [c["customer_id"] for c in customers]

    orders = orders_generator.generate_orders(customer_segments)
    write_csv("orders.csv", orders, [
        "order_id", "customer_id", "order_date", "order_status",
        "total_amount", "discount_percent", "shipping_cost"])

    items = items_generator.generate_order_items(orders)
    write_csv("order_items.csv", items, [
        "order_item_id", "order_id", "product_id", "product_name",
        "product_category", "quantity", "unit_price", "line_total"])

    reviews = reviews_generator.generate_reviews(customer_ids)
    write_csv("product_reviews.csv", reviews, [
        "review_id", "product_id", "customer_id", "review_date", "rating",
        "review_title", "review_text", "verified_purchase"])

    tickets = tickets_generator.generate_tickets(customer_ids)
    write_csv("support_tickets.csv", tickets, [
        "ticket_id", "customer_id", "ticket_date", "category", "priority",
        "subject", "description", "resolution", "status"])

    print("Done.")


if __name__ == "__main__":
    main()
