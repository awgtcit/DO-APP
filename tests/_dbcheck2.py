import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=172.50.35.75;"
    "DATABASE=mtcintranet;"
    "UID=sa;PWD=Admin@123"
)
cursor = conn.cursor()

# Check Intra_Users columns
cursor.execute("SELECT TOP 0 * FROM Intra_Users")
print("=== Intra_Users columns ===")
for col in cursor.description:
    print(f"  {col[0]} ({col[1].__name__})")

# Check sathish user
cursor.execute("SELECT * FROM Intra_Users WHERE FirstName LIKE '%sathish%' OR LastName LIKE '%narasimhan%'")
rows = cursor.fetchall()
cols = [c[0] for c in cursor.description]
for row in rows:
    print("\n=== Sathish's record ===")
    for c, v in zip(cols, row):
        print(f"  {c}: {v}")

# Check Module_AccessGroup
cursor.execute("SELECT TOP 0 * FROM Intra_Module_AccessGroup")
print("\n=== Intra_Module_AccessGroup columns ===")
for col in cursor.description:
    print(f"  {col[0]} ({col[1].__name__})")

cursor.execute("SELECT TOP 10 * FROM Intra_Module_AccessGroup")
rows = cursor.fetchall()
cols = [c[0] for c in cursor.description]
print("\n=== AccessGroup data ===")
for row in rows:
    print(dict(zip(cols, row)))

# Check DMS Permission
cursor.execute("SELECT TOP 0 * FROM Intra_DMS_Permission")
print("\n=== DMS Permission columns ===")
for col in cursor.description:
    print(f"  {col[0]} ({col[1].__name__})")

# Check credentials for sathish
cursor.execute("SELECT * FROM Intra_UserCredentials WHERE CredUsername LIKE '%sathish%' OR CredEmail LIKE '%sathish%'")
rows = cursor.fetchall()
cols = [c[0] for c in cursor.description]
for row in rows:
    print("\n=== Sathish's credentials ===")
    for c, v in zip(cols, row):
        if c != 'CredPassword':
            print(f"  {c}: {v}")
        else:
            print(f"  {c}: {'***' + str(v)[-10:] if v else 'NULL'}")

# Sample IT Support data
cursor.execute("SELECT TOP 5 * FROM Intra_ITSupport ORDER BY id DESC")
rows = cursor.fetchall()
cols = [c[0] for c in cursor.description]
print("\n=== Sample IT tickets ===")
for row in rows:
    print(dict(zip(cols, row)))

conn.close()
