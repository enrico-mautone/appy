from datetime import date, datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Query, Response, Security, Request
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import DateTime, create_engine, func, inspect, select, MetaData, Table, text, true
from sqlalchemy.engine import reflection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import and_
from collections import defaultdict
import networkx as nx
import matplotlib.pyplot as plt
import io
import os
import importlib.util
from jose import JWTError, jwt
import threading


app = FastAPI()

security = HTTPBearer(auto_error=False) 

def load_config_var(varname,default_value):
    return os.getenv(varname,default_value)

VERIFY_TOKEN = load_config_var('VERIFY_TOKEN',False)
SECRET_KEY = load_config_var('SECRET_KEY','')
ALGORITHM = load_config_var('ALGORITHM','')
DATABASE_URL = load_config_var('DATABASE_URL','')
SCHEMA = load_config_var('SCHEMA','')
SCHEMA_TABLES = load_config_var('TABLES',[]).split(',')

async def verify_user_session(token: HTTPAuthorizationCredentials = Security(security), verify_token: bool = VERIFY_TOKEN) -> dict:
    if not verify_token:        
        return {"user": "anonymous"}
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid JWT token")



engine = create_engine(f"{DATABASE_URL}")
metadata = MetaData()

inspector = inspect(engine)

if not SCHEMA_TABLES or  len(SCHEMA_TABLES) == 0:
    all_tables = inspector.get_table_names(schema=SCHEMA)
    SCHEMA_TABLES = [[table, table, None] for table in all_tables]
else:
    selected_tables = [[table, table, None] for table in SCHEMA_TABLES]
    SCHEMA_TABLES = selected_tables


tables = {}
for table_name, alias, id_field in SCHEMA_TABLES:
    table = Table(table_name, metadata, autoload_with=engine, schema=SCHEMA)
    pk_columns = inspector.get_pk_constraint(table_name, schema=SCHEMA)["constrained_columns"]
    id_field = pk_columns[0] if pk_columns else None
    tables[alias.lower()] = (table, table_name, id_field)

def run_db_query(query, is_select=False):
    with engine.connect() as connection:
        if is_select:
            print("query: %s" % query)
            result = connection.execute(query).mappings().all()
            return [dict(row) for row in result]
        else:
            result = connection.execute(query)
            return result.rowcount

@app.get("/stored_procedures")
async def get_stored_procedures():
    sql = text("""
    SELECT
    SCHEMA_NAME(p.schema_id) AS schema_name,
    p.name AS procedure_name,
    STRING_AGG(
        CONCAT(
            '@', pa.name, ' ', t.name,
            CASE
                WHEN t.name IN ('varchar', 'nvarchar', 'varbinary') THEN CONCAT('(', pa.max_length, ')')
                ELSE ''
            END,
            CASE
                WHEN pa.is_nullable = 1 THEN ' NULLABLE'
                ELSE ' NOT NULLABLE'
            END,
            CASE
                WHEN pa.has_default_value = 1 THEN CONCAT(' DEFAULT ', CONVERT(VARCHAR(MAX), pa.default_value))
                ELSE ''
            END
        ),
        ', '
    ) WITHIN GROUP (ORDER BY pa.parameter_id) AS parameters
FROM
    sys.procedures p
    JOIN sys.parameters pa ON p.object_id = pa.object_id
    JOIN sys.types t ON pa.user_type_id = t.user_type_id
WHERE
    pa.name IS NOT NULL
GROUP BY
    p.schema_id, p.name
ORDER BY
    p.name
    """)

    response_lines = [f"SCHEMA: {SCHEMA}\n\n", "#\tStored Procedure Name\t\tParameters\n", "-" * 115 + "\n"]
    
    with engine.connect() as conn:
        results = conn.execute(sql).fetchall()
        for index, (schema_name, procedure_name, parameters) in enumerate(results, start=1):
            # Formattazione dei parametri rimuovendo doppie virgolette
            parameters = parameters.replace('\"', '')
            # Allineamento del nome della stored procedure e dei parametri
            line = f"{index:<2}\t{procedure_name:<35}\t{parameters}\n"
            response_lines.append(line)

    response_text = "".join(response_lines)
    return Response(content=response_text, media_type="text/plain")
  
        
@app.get("/procedure/{procedure_name}")
async def execute_procedure(procedure_name: str, request: Request):
    # Estrai i parametri dalla query
    params = dict(request.query_params)
    
    # Costruisce dinamicamente la stringa di parametri per la stored procedure
    sql_params = ", ".join([f"@{k} = :{k}" for k in params.keys()])

    # Prepara la query SQL dinamicamente, inclusi i parametri
    sql = text(f"EXEC {procedure_name} {sql_params}")

    result_list = []

    # Esegue la query passando i parametri come un dizionario
    with engine.connect() as conn:
        result = conn.execute(sql, params).mappings().all()
        result_list = [dict(row) for row in result]

    return result_list
        

@app.get("/schema_diagram")
async def get_db_schema_diagram(width: float = Query(12, alias="width"), height: float = Query(12, alias="height"),table_name: str = Query('', alias="table_name")):
    img = generate_schema_graph(engine,width,height,table_name)
    return Response(content=img.read(), media_type="image/png")
    
@app.get("/table_definition/{table_name}", response_class=PlainTextResponse)
async def table_definition(table_name: str):
    print("table_definition %s" % table_name)
    table_info = get_table_info(engine, table_name)
    
    if table_info is None:
        raise HTTPException(status_code=404, detail="Table not found")

    # Formatta le informazioni in una tabella plain text
    headers = ["Name", "Type", "Primary Key", "Nullable", "Default"]
    max_length = {header: len(header) for header in headers}
    for column in table_info:
        for key, value in column.items():
            max_length[key] = max(max_length[key], len(str(value)))
    
    header_row = " | ".join(header.ljust(max_length[header]) for header in headers)
    separator = "-|-".join("-" * max_length[header] for header in headers)

    num_records = get_num_records(engine,table_name)

    # Prepara la riga con il nome della tabella e il numero di record
    table_name_row = f"TABLE: {table_name}\t(Records: {num_records})"
    rows = [table_name_row, header_row, separator]
    
    for column in table_info:
        row = " | ".join(str(column[header]).ljust(max_length[header]) for header in headers)
        rows.append(row)

    return "\n".join(rows)

@app.get("/table_relationships", response_class=PlainTextResponse)
async def table_relationships():
    relationships = get_table_relationships(engine)
    # Calcola la larghezza massima per il nome della tabella per l'allineamento
    max_table_name_length = 50
    max_relations_list_length = 70

    # Costruisci l'header della tabella per la risposta
    header = f"SCHEMA: {SCHEMA}\n\n"
    header += f"{'Nome Tabella':<{max_table_name_length}} {'Relazioni':<{max_relations_list_length}}\n"
    header += "-" * (max_table_name_length + max_relations_list_length + 1) + "\n"  # Una linea di separazione

    # Costruzione del corpo della risposta con i dettagli delle relazioni
    body = ""
    for table, related_tables in relationships.items():
        relations_str = ", ".join(related_tables)
        body += f"{table:<{max_table_name_length}} {relations_str:<{max_relations_list_length}}\n"

    return Response(content=header + body, media_type="text/plain")

@app.get("/tables", response_class=PlainTextResponse)
async def get_available_tables():
    # Preparazione dell'header della tabella per la risposta
    header = f"SCHEMA: {SCHEMA}"
    header += "\n\n"
    header += f"{'#':<10} {'Nome Tabella':<50} {'ID Field':<20}\n"
    header += "-" * 100 + "\n"  # Una linea di separazione

    # Costruzione del corpo della risposta con i dettagli delle tabelle
    body = ""
    cnt=1
    for alias,(table, table_name, id_field) in tables.items():
        table_name = table.name  # Assumendo che 'table' abbia l'attributo 'name'
        body += f"{cnt:<10} {table_name:<50} {id_field or 'ID non specificato':<20}\n"
        cnt = cnt+1

    return Response(content=header + body, media_type="text/plain")

@app.post("/{alias}")
async def create_item(alias: str, item: dict, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias.lower(), (None, None, None))
    if not table_name:
        raise HTTPException(status_code=404, detail="Table not found")
    query = table.insert().values(**item)
    last_record_id = None

    def run():
        nonlocal last_record_id
        with engine.begin() as conn: 
            last_record_id = conn.execute(query).inserted_primary_key[0]
            conn.commit()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    return_query = select(table).where(getattr(table.c, id_field) == last_record_id)
    created_item = run_db_query(return_query, is_select=True)
    if not created_item:
        raise HTTPException(status_code=404, detail="Created item not found")
    return created_item[0]

@app.get("/{alias}")
async def read_all_items(alias: str, request:Request,context: dict = Depends(verify_user_session)):

    table, table_name, id_field = tables.get(alias.lower(), (None, None, None))
    if not table_name:
        raise HTTPException(status_code=404, detail="Table not found")
    
    query_params = dict(request.query_params)

    print(f"query_params = {query_params}") 

    where_clause = build_where_clause(table, query_params)

    print(f"where_clause = {where_clause}")

    if where_clause.compare(true()):
        query = select(table)
    else:
        query = select(table).where(where_clause)

    result = None
    def run():
        nonlocal result
        result = run_db_query(query, is_select=True)
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if not result:
        raise HTTPException(status_code=404, detail=f"No Records found in table: {table_name}")
    return result

@app.get("/{alias}/{item_id}")
async def read_item(alias: str, item_id: int, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias.lower(), (None, None, None))
    if not table_name:
        raise HTTPException(status_code=404, detail="Table not found")
    query = select(table).where(getattr(table.c, id_field) == item_id) 
    result = None
    def run():
        nonlocal result
        result = run_db_query(query, is_select=True)
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if not result:
        raise HTTPException(status_code=404, detail="Item not found")
    return result

@app.put("/{alias}/{item_id}")
async def update_item(alias: str, item_id: int, item: dict, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias.lower(), (None, None, None))
    if not table_name:
        raise HTTPException(status_code=404, detail="Table not found")
    update_query = table.update().where(getattr(table.c, id_field) == item_id).values(**item)
    def run_update():
        with engine.begin() as conn:
            conn.execute(update_query)
            conn.commit()

    thread = threading.Thread(target=run_update)
    thread.start()
    thread.join()
    return_query = select(table).where(getattr(table.c, id_field) == item_id)
    updated_item = run_db_query(return_query, is_select=True)
    if not updated_item:
        raise HTTPException(status_code=404, detail="Updated item not found")
    return updated_item[0]

@app.delete("/{alias}/{item_id}")
async def delete_item(alias: str, item_id: int, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias.lower(), (None, None, None))
    if not table_name:
        raise HTTPException(status_code=404, detail="Table not found")
    get_query = select(table).where(getattr(table.c, id_field) == item_id)
    item_to_delete = run_db_query(get_query, is_select=True)
    if not item_to_delete:
        raise HTTPException(status_code=404, detail="Item to delete not found")
    delete_query = table.delete().where(getattr(table.c, id_field) == item_id)
    def run_delete():
        with engine.begin() as conn:
            conn.execute(delete_query)
            conn.commit()
    thread = threading.Thread(target=run_delete)
    thread.start()
    thread.join()
    return item_to_delete[0]

def get_table_relationships(engine):
    inspector = reflection.Inspector.from_engine(engine)
    relationships = defaultdict(list)

    # Itera su tutte le tabelle
    for table_name in inspector.get_table_names():

        table_found = False
        for record in SCHEMA_TABLES:
            if table_name.lower() == record[0].lower(): 
                table_found = True
                break
        if table_found == False:
            continue
    
        # Ottieni le informazioni sulle chiavi esterne per ciascuna tabella
        fk_info = inspector.get_foreign_keys(table_name)
        if not fk_info:
            continue

        for fk in fk_info:
            # Costruisci una mappa delle relazioni
            # chiave: tabella corrente, valore: lista di tabelle a cui è collegata tramite chiavi esterne
            relationships[table_name].append(fk['referred_table'])
    return relationships

def build_where_clause(table, query_params):
    conditions = []
    for field, value in query_params.items():
        field_lower = field.lower()
        if field_lower in {f.lower() for f in table.c.keys()}:
            column = getattr(table.c, field)
            if isinstance(column.type, DateTime):
                try:
                    # Crea un oggetto datetime dal parametro della query
                    value_datetime = datetime.fromisoformat(value)
                    # Aggiungi un giorno al valore della data per creare un intervallo
                    next_day = value_datetime + timedelta(days=1)
                    # Crea una condizione per selezionare i record entro questo intervallo
                    conditions.append(column >= value_datetime)
                    conditions.append(column < next_day)
                except ValueError:
                    # Se la conversione fallisce, ignora questo parametro
                    continue
            else:
                conditions.append(column == value)
    
    if not conditions:
        return true()
    return and_(*conditions)

def get_table_info(engine, table_name):

    table_found = False
    for record in SCHEMA_TABLES:
        if table_name.lower() == record[0].lower():  # Assumendo che il nome della tabella sia il primo elemento di ogni record
            table_found = True
            break
    if table_found == False:
        return None
    
    metadata = MetaData()
    metadata.reflect(engine, only=[table_name])
    table = metadata.tables.get(table_name)
    if table_name not in metadata.tables:
        return None  # La tabella non esiste

    columns_info = []
    for column in table.columns:
        column_info = {
            "Name": column.name,
            "Type": str(column.type),
            "Primary Key": column.primary_key,
            "Nullable": column.nullable,
            "Default": str(column.default)
        }
        columns_info.append(column_info)
    return columns_info


def get_num_records(engine,table_name):
    metadata = MetaData()
    metadata.reflect(engine, only=[table_name])
    table = metadata.tables.get(table_name)
    if table_name not in metadata.tables:
        return 0  # La tabella non esiste

    try:
        with engine.connect() as connection:
            num_records_query = select(func.count()).select_from(table)
            result = connection.execute(num_records_query)
            num_records = result.scalar()  # Ottiene il primo valore del risultato, che sarà il conteggio
            return num_records
    except SQLAlchemyError as e:
        print(f"Errore nell'esecuzione della query di conteggio: {e}")
        return 0

def generate_schema_graph(engine, width: float = 12, height: float = 12, table_name_param: str = ''):
    metadata = MetaData()
    
    if table_name_param:
        # Rifletti solo la tabella specificata
        metadata.reflect(bind=engine, only=[table_name_param])
    else:
        # Rifletti lo schema bindando qui per tutte le tabelle
        metadata.reflect(bind=engine)

    G = nx.DiGraph()

    for table_name in metadata.tables:
        G.add_node(table_name)

    for table_name, table in metadata.tables.items():
        for fk in table.foreign_keys:
            if table_name == table_name_param or fk.column.table.name == table_name_param or table_name_param == '':
                G.add_edge(fk.column.table.name, table_name, label=f"{fk.parent.name} -> {fk.column.name}")

    pos = nx.spring_layout(G)  # Posizionamento dei nodi
    plt.figure(figsize=(width, height))  # Definisci la dimensione della figura
    nx.draw(G, pos, with_labels=True, node_size=2000, node_color="lightblue", font_size=10, font_weight="bold")
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color='red')

    img = io.BytesIO()  # Crea un buffer per l'immagine
    plt.savefig(img, format='PNG')  # Salva il grafico nel buffer come PNG
    img.seek(0)  # Sposta il cursore all'inizio del buffer
    plt.close()  # Chiudi la figura per liberare memoria
    return img

async def execute_stored_procedure(engine, procedure_name: str, **kwargs):
    with engine.connect() as connection:
        # Costruisci la query per eseguire la stored procedure
        query = f"CALL {procedure_name}("
        query += ", ".join([f":{key}" for key in kwargs.keys()])
        query += ");"
        try:
            result = connection.execute(text(query), **kwargs)
            # Assumendo che la stored procedure possa restituire dei risultati
            result_set = result.fetchall()
            return [dict(row) for row in result_set]
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


    
@app.get("/", response_class=PlainTextResponse)
async def root():
    return "Welcome to Appy!"

