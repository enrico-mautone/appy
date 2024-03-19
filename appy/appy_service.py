# appy/appy_service.py
import uvicorn
import config
from appy.appy import app


def run_server(config_path='config/config.py'):
 
    uvicorn.run(app, host=config.SERVICE_IP, port=config.SERVICE_PORT)

if __name__ == "__main__":
    run_server()
