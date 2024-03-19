@echo off
REM Imposta le variabili di ambiente permanentemente per l'utente corrente


setx APPY_CONFIG_PATH ".\config.py"

setx APPY_SERVICE_IP "127.0.0.1"


setx APPY_SERVICE_PORT "8000"

setx APPY_SECRET_KEY "YOUR_SECRET_KEY"
setx APPY_ALGORITHM "HS256"
setx APPY_VERIFY_TOKEN False
setx DATABASE_URL "mssql+pyodbc://sa:password01!@WINDELL-186CUHK\SQLEXPRESS/NAUS_PROD?driver=ODBC+Driver+17+for+SQL+Server"
setx SCHEMA "dbo"
setx TABLES "affitti,clienti"

echo Le variabili di ambiente sono state impostate.
