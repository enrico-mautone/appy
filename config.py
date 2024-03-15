# DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"
# DATABASE_URL = "mysql+aiomysql://user:password@localhost/dbname"
# DATABASE_URL = "sqlite+aiosqlite:///./test.db"
DATABASE_URL = "mssql+pyodbc://username:password@DBSERVER/CATALOG?driver=YOUR_ODBC_FRIVER"
TABLE_NAME = "TABLE_NAME"
ENDPOINT_ALIAS = "table_alias_for_endpoint"  # Oppure "utenti", se vuoi specificare un alias
ID_FIELD_NAME = "table_id_field" 
FINAL_ENDPOINT = ENDPOINT_ALIAS or TABLE_NAME
SECRET_KEY = "YOUR_SECRET_KEY"
ALGORITHM = "HS256"
VERIFY_TOKEN = False  
