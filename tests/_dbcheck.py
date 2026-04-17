import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=172.50.35.75;"
    "DATABASE=mtcintranet;"
    "UID=sa;PWD=Admin@123"
)
cursor = conn.cursor()

# Check if Intra_ITSupport table exists
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME LIKE '%ITSupport%' OR TABLE_NAME LIKE '%IT_Support%' OR TABLE_NAME LIKE '%ITsupport%'
""")
print("=== IT Support tables ===")
for row in cursor.fetchall():
    print(row[0])

# Check all tables with 'IT' or 'Support' in name
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME LIKE '%IT%' OR TABLE_NAME LIKE '%Support%' OR TABLE_NAME LIKE '%support%'
""")
print("\n=== Tables with IT/Support ===")
for row in cursor.fetchall():
    print(row[0])

# Check Intra_ITSupport if exists
try:
    cursor.execute("SELECT TOP 0 * FROM Intra_ITSupport")
    cols = [col[0] for col in cursor.description]
    print("\n=== Intra_ITSupport columns ===")
    for c in cols:
        print(f"  {c}")
except Exception as e:
    print(f"\nIntra_ITSupport doesn't exist: {e}")

# List ALL tables
cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
print("\n=== ALL tables ===")
for row in cursor.fetchall():
    print(f"  {row[0]}")

conn.close()
