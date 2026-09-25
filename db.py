import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Read-only connection to AIJobMarket as rag_reader."""
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost\\SQLEXPRESS;"
        f"DATABASE=AIJobMarket;UID=rag_reader;PWD={os.getenv('RAG_DB_PASSWORD')};"
        "TrustServerCertificate=yes;"
    )
    conn.timeout = 30  # kills any query running longer than 30s
    return conn
