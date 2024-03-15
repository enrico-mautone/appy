from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text, select, MetaData, Table
from jose import JWTError, jwt
from typing import Optional
import config
import threading

security = HTTPBearer(auto_error=False) 

async def verify_user_session(token: HTTPAuthorizationCredentials = Security(security), verify_token: bool = config.VERIFY_TOKEN) -> dict:
    if not verify_token:
        # Se la verifica del token è disabilitata, ritorna immediatamente un utente anonimo o un payload di default
        return {"user": "anonymous"}
    
    # Altrimenti, procedi con la verifica del token JWT
    try:
        payload = jwt.decode(token.credentials, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid JWT token")

app = FastAPI()

# SQLAlchemy engine
engine = create_engine(config.DATABASE_URL)
metadata = MetaData()
table = Table(config.TABLE_NAME, metadata, autoload_with=engine)


def run_db_query(query, is_select=False):
    with engine.connect() as connection:
        if is_select:
            result = connection.execute(query).mappings().all()
            return [dict(row) for row in result]
        else:
            result = connection.execute(query)
            # Qui potresti voler gestire il risultato per operazioni non di selezione
            return result.rowcount  # per esempio, il numero di righe influenzate



@app.post("/{FINAL_ENDPOINT}")
async def create_item(FINAL_ENDPOINT: str, item: dict, context: dict = Depends(verify_user_session)):
    # Costruisci la query per inserire l'oggetto
    query = table.insert().values(**item)
    last_record_id = None

    def run():
        nonlocal last_record_id
        with engine.begin() as conn:  # Utilizza una transazione
            last_record_id = conn.execute(query).inserted_primary_key[0]
            conn.commit()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()

    # Recupera l'oggetto appena creato utilizzando l'ID restituito
    return_query = select(table).where(getattr(table.c, config.ID_FIELD_NAME) == last_record_id)
    created_item = run_db_query(return_query, is_select=True)

    if not created_item:
        raise HTTPException(status_code=404, detail="Created item not found")
    return created_item[0]

@app.get("/{FINAL_ENDPOINT}")
async def read_all_items(FINAL_ENDPOINT: str, context: dict = Depends(verify_user_session)):
    query = select(table)  # Usa direttamente `table` senza racchiuderlo in una lista
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

@app.get("/{FINAL_ENDPOINT}/{item_id}")
async def read_item(FINAL_ENDPOINT: str, item_id: int, context: dict = Depends(verify_user_session)):
    # Utilizza il nome del campo ID configurabile nella query
    query = select(table).where(getattr(table.c, config.ID_FIELD_NAME) == item_id) 
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

@app.put("/{FINAL_ENDPOINT}/{item_id}")
async def update_item(FINAL_ENDPOINT: str, item_id: int, item: dict, context: dict = Depends(verify_user_session)):
    update_query = table.update().where(getattr(table.c, config.ID_FIELD_NAME) == item_id).values(**item)

    def run_update():
        with engine.begin() as conn:
            conn.execute(update_query)
            conn.commit()

    thread = threading.Thread(target=run_update)
    thread.start()
    thread.join()

    # Recupera l'oggetto aggiornato
    return_query = select(table).where(getattr(table.c, config.ID_FIELD_NAME) == item_id)
    updated_item = run_db_query(return_query, is_select=True)

    if not updated_item:
        raise HTTPException(status_code=404, detail="Updated item not found")
    return updated_item[0]

@app.delete("/{FINAL_ENDPOINT}/{item_id}")
async def delete_item(FINAL_ENDPOINT: str, item_id: int, context: dict = Depends(verify_user_session)):
    # Recupera prima l'oggetto da eliminare
    get_query = select(table).where(getattr(table.c, config.ID_FIELD_NAME) == item_id)
    item_to_delete = run_db_query(get_query, is_select=True)

    if not item_to_delete:
        raise HTTPException(status_code=404, detail="Item to delete not found")

    delete_query = table.delete().where(getattr(table.c, config.ID_FIELD_NAME) == item_id)

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
    uvicorn.run(app, host="127.0.0.1", port=8000)