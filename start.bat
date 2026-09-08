@echo off
echo Starting ARQAU backend...
cd backend
start "ARQAU Backend" cmd /k "uvicorn app.main:app --reload --port 8000"
cd ..
echo Starting ARQAU frontend...
start "ARQAU Frontend" cmd /k "npm run dev"
echo Both services are starting.
echo Frontend: http://localhost:3000
echo Backend: http://localhost:8000
