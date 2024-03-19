# appy/appy_service.py
import os
import uvicorn

from appy.appy import app


def run_server():

    service_ip = os.getenv("APPY_SERVICE_IP", "default_ip")
    service_port = os.getenv("APPY_SERVICE_PORT", "default_port")

    print(f"Starting appy server on ip %s port %s" % (service_ip,service_port) ) 
    uvicorn.run(app, host=service_ip, port=service_port)

if __name__ == "__main__":
    run_server()
