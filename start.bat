@echo off
echo Starting backend...
start "Backend - FastAPI" cmd /k "py -3.13 -m uvicorn app_server:app --reload --port 8000"

echo Starting frontend...
start "Frontend - React" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers are starting.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo.
timeout /t 3 >nul
start http://localhost:5173
