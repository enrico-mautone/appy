# config.py
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"
# DATABASE_URL = "mysql+aiomysql://user:password@localhost/dbname"
# DATABASE_URL = "sqlite+aiosqlite:///./test.db"
# DATABASE_URL = "mssql+pyodbc://user:password@database_url/catalog?driver=your_odbc_driver"

schema_config = {
    "schema": "dbo",
    "tables": [
        # ["table_name", "endpoint_alias"],
        
    ]
}

# API CONFIGURATION
SERVICE_PORT=8000
SERVICE_IP='0.0.0.0'
SECRET_KEY = "YOUR_SECRET_KEY"
ALGORITHM = "HS256"
VERIFY_TOKEN = False  # True to enable token verification



schema_config = {
    "schema": "dbo",
    "tables": [
        # ["table_name", "endpoint_alias"],
        
    ]
}

# API CONFIGURATION
SERVICE_PORT=8000
SECRET_KEY = "YOUR_SECRET_KEY"
ALGORITHM = "HS256"
VERIFY_TOKEN = False  # True to enable token verification
