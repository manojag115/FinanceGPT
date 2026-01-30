import psycopg2

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="financegpt",
    user="postgres",
    password="postgres"
)

cur = conn.cursor()

# Count accounts
cur.execute("SELECT COUNT(*) FROM investment_accounts;")
account_count = cur.fetchone()[0]
print(f"Investment Accounts: {account_count}")

# Count holdings
cur.execute("SELECT COUNT(*) FROM investment_holdings;")
holding_count = cur.fetchone()[0]
print(f"Investment Holdings: {holding_count}")

# Get total value
cur.execute("SELECT SUM(market_value) FROM investment_holdings;")
total_value = cur.fetchone()[0] or 0
print(f"Total Market Value: ${total_value:,.2f}")

# List accounts if any
if account_count > 0:
    cur.execute("SELECT account_name, total_value FROM investment_accounts;")
    print("\nAccounts:")
    for row in cur.fetchall():
        print(f"  - {row[0]}: ${row[1]:,.2f}")

# List holdings if any
if holding_count > 0:
    cur.execute("SELECT symbol, quantity, market_value FROM investment_holdings;")
    print("\nHoldings:")
    for row in cur.fetchall():
        print(f"  - {row[0]}: qty={row[1]}, value=${row[2]:,.2f}")

cur.close()
conn.close()
