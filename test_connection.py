import os, pyodbc
from dotenv import load_dotenv
load_dotenv()

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost\\SQLEXPRESS;"
    f"DATABASE=JobMarket;UID=rag_reader;PWD={os.getenv('RAG_DB_PASSWORD')};"
    "TrustServerCertificate=yes;"
)
conn.timeout = 30

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM dbo.jobs")
print("Connected. Jobs in table:", cursor.fetchone()[0])
conn.close()