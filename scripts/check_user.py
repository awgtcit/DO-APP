import pyodbc, os
c = pyodbc.connect(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.environ['DB_SERVER']};DATABASE={os.environ['DB_NAME']};"
    f"UID={os.environ['DB_USER']};PWD={os.environ['DB_PASSWORD']}"
)
cur = c.cursor()
cur.execute("SELECT u.EmpID, u.UserName, u.EmailAddress, ISNULL(cr.CredEmail,'') FROM Intra_Users u LEFT JOIN Intra_UserCredentials cr ON cr.EmpID = u.EmpID WHERE u.UserName = 'sathish.narasimhan'")
r = cur.fetchone()
if r:
    print(f"EmpID={r[0]}  User={r[1]}  EmailAddress={r[2]}  CredEmail={r[3]}")
else:
    print("NOT FOUND")
