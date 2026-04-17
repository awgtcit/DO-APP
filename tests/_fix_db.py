import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=172.50.35.75;"
    "DATABASE=mtcintranet;"
    "UID=sa;PWD=Admin@123"
)
c = conn.cursor()

# Add status column
try:
    c.execute("ALTER TABLE Intra_ITSupport ADD [status] VARCHAR(20) DEFAULT 'open' NOT NULL")
    conn.commit()
    print("Added status column")
except Exception as e:
    print(f"Status column: {e}")

# Update existing rows
try:
    c.execute("UPDATE Intra_ITSupport SET [status] = 'open' WHERE [status] IS NULL OR [status] = ''")
    conn.commit()
    print("Updated existing rows")
except Exception as e:
    print(f"Update: {e}")

# Verify
c.execute("SELECT TOP 0 * FROM Intra_ITSupport")
print("Columns:", [col[0] for col in c.description])
c.execute("SELECT TOP 3 id, requester, subject, [status] FROM Intra_ITSupport")
for row in c.fetchall():
    print(row)

conn.close()
