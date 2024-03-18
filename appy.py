from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text, select, MetaData, Table
from sqlalchemy.engine.reflection import Inspector
from jose import JWTError, jwt
from typing import Optional
import config
import threading

security = HTTPBearer(auto_error=False) 

async def verify_user_session(token: HTTPAuthorizationCredentials = Security(security), verify_token: bool = config.VERIFY_TOKEN) -> dict:
    if not verify_token:        
        return {"user": "anonymous"}
    try:
        payload = jwt.decode(token.credentials, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid JWT token")

app = FastAPI()

engine = create_engine(f"{config.DATABASE_URL}")
metadata = MetaData()

inspector = Inspector.from_engine(engine)

if not config.schema_config["tables"] or  len(config.schema_config["tables"]) == 0:
    all_tables = inspector.get_table_names(schema=config.schema_config["schema"])
    config.schema_config["tables"] = [[table, table, None] for table in all_tables]


tables = {}
for table_name, alias, id_field in config.schema_config["tables"]:
    table = Table(table_name, metadata, autoload_with=engine, schema=config.schema_config["schema"])
    pk_columns = inspector.get_pk_constraint(table_name, schema=config.schema_config["schema"])["constrained_columns"]
    id_field = pk_columns[0] if pk_columns else None
    tables[alias] = (table, table_name, id_field)

def run_db_query(query, is_select=False):
    with engine.connect() as connection:
        if is_select:
            print("query: %s" % query)
            result = connection.execute(query).mappings().all()
            return [dict(row) for row in result]
        else:
            result = connection.execute(query)
            return result.rowcount  


@app.post("/{alias}")
async def create_item(alias: str, item: dict, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias, (None, None, None))
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
async def read_all_items(alias: str, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias, (None, None, None))
    if not table_name:
        raise HTTPException(status_code=404, detail="Table not found")
    query = select(table) 
    result = None
    def run():
        nonlocal result
        result = run_db_query(query, is_select=True)
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if not result:
        raise HTTPException(status_code=404, detail="No items found")
    return result

@app.get("/{alias}/{item_id}")
async def read_item(alias: str, item_id: int, context: dict = Depends(verify_user_session)):
    table, table_name, id_field = tables.get(alias, (None, None, None))
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
    table, table_name, id_field = tables.get(alias, (None, None, None))
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
    table, table_name, id_field = tables.get(alias, (None, None, None))
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.SERVICE_PORT)