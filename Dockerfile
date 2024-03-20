# Scegli l'immagine base. Python 3.8 è un buon punto di partenza.
FROM python:3.8

# Imposta la directory di lavoro nel container
WORKDIR /appy

# Clona il repository GitHub e installa il pacchetto appy.
# Sostituisci <branch> con il branch desiderato o utilizza la versione principale
RUN pip install git+https://github.com/enrico-mautone/appy.git@main

# Definisci le variabili di ambiente. Puoi utilizzare ENV per impostarle.
# Per TABLES e altre variabili che richiedono valori complessi, usa la serializzazione.
ENV APPY_SERVICE_IP="127.0.0.1" \
    APPY_SERVICE_PORT="8000" \
    APPY_SECRET_KEY="YOUR_SECRET_KEY" \
    APPY_ALGORITHM="HS256" \
    APPY_VERIFY_TOKEN="False" \
    DATABASE_URL="mssql+pyodbc://sa:password01!@host.docker.internal\SQLEXPRESS/NAUS_PROD?driver=ODBC+Driver+17+for+SQL+Server" \
    SCHEMA="dbo" \
    TABLES="affitti,clienti,letture"

# Espone la porta su cui il servizio è in ascolto
EXPOSE ${APPY_SERVICE_PORT}

# Aggiungi Microsoft repository per il driver ODBC di SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update
# Installa unixODBC, necessario per pyodbc
RUN apt-get install -y unixodbc-dev
# Installa il driver ODBC di Microsoft per SQL Server
RUN ACCEPT_EULA=Y apt-get install -y msodbcsql17


# Comando per eseguire l'applicazione
# Assumi che il comando per eseguire il tuo servizio sia 'appy'.
# Se hai un comando/script specifico per l'avvio, aggiustalo di conseguenza.
CMD ["appy"]
