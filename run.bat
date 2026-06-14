@echo off
REM Launch the Crane Lifting Study Tool locally. Double-click this file, or run it from a terminal.
REM Keep the window that opens; closing it stops the tool. Your browser opens at http://localhost:8501
set "PY=C:\Users\tyu\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%~dp0"
"%PY%" -m streamlit run app.py --server.port=8501
pause
