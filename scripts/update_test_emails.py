"""Update all test user emails to m.nizar@awgtc.com"""
import pyodbc, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.environ['DB_SERVER']};DATABASE={os.environ['DB_NAME']};"
    f"UID={os.environ['DB_USER']};PWD={os.environ['DB_PASSWORD']}"
)
cur = conn.cursor()

emp_ids = [900101, 900102, 900103, 900104, 900105, 900106, 900107, 900108]
placeholders = ",".join("?" for _ in emp_ids)
new_email = "m.nizar@awgtc.com"

cur.execute(f"UPDATE Intra_Users SET EmailAddress = ? WHERE EmpID IN ({placeholders})", [new_email] + emp_ids)
print(f"Users updated: {cur.rowcount}")

cur.execute(f"UPDATE Intra_UserCredentials SET CredEmail = ? WHERE EmpID IN ({placeholders})", [new_email] + emp_ids)
print(f"Creds updated: {cur.rowcount}")

conn.commit()

cur.execute(f"SELECT EmpID, UserName, EmailAddress FROM Intra_Users WHERE EmpID IN ({placeholders}) ORDER BY EmpID", emp_ids)
for r in cur.fetchall():
    print(f"  {r[1]:18s}  {r[2]}")

conn.close()
print("Done.")
