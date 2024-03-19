@echo off
REM Imposta le variabili di ambiente permanentemente per l'utente corrente

REM Imposta APPY_CONFIG_PATH
setx APPY_CONFIG_PATH ".\config.py"

REM Imposta SERVICE_IP
setx APPY_SERVICE_IP "127.0.0.1"

REM Imposta SERVICE_PORT
setx APPY_SERVICE_PORT "8000"

echo Le variabili di ambiente sono state impostate.
