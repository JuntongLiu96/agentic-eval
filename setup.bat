@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo.
echo ============================================================
echo   AgenticEval - Windows Setup
echo ============================================================
echo.

:: ---- Check uv ----
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/5] uv not found. Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install uv. Please install manually:
        echo   https://docs.astral.sh/uv/getting-started/installation/
        exit /b 1
    )
    :: Refresh PATH so uv is available in this session
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
    where uv >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: uv installed but not found on PATH. Please restart your terminal and run setup.bat again.
        exit /b 1
    )
    echo   uv installed successfully.
) else (
    echo [1/5] uv found.
)

:: ---- Check Node.js ----
set "HAS_NODE=0"
where node >nul 2>&1
if %errorlevel% equ 0 (
    echo [2/5] Node.js found.
    set "HAS_NODE=1"
) else (
    echo [2/5] Node.js not found. Frontend setup will be skipped.
    echo   Install Node.js 18+ from https://nodejs.org/ if you need the web dashboard.
)

:: ---- Backend setup ----
echo.
echo [3/5] Setting up backend...

pushd "%~dp0backend"

if not exist ".venv" (
    echo   Creating virtual environment...
    uv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        popd
        exit /b 1
    )
)

echo   Installing dependencies...
uv pip install -e ".[dev]"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install backend dependencies.
    popd
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo   Created .env from .env.example
        echo   Edit backend\.env to configure your judge LLM ^(JUDGE_MODEL, JUDGE_API_KEY, JUDGE_BASE_URL^)
    )
) else (
    echo   .env already exists, skipping.
)

popd
echo   Backend setup complete.

:: ---- Frontend setup ----
echo.
if %HAS_NODE% equ 1 (
    echo [4/5] Setting up frontend...
    pushd "%~dp0frontend"
    call npm install
    if %errorlevel% neq 0 (
        echo WARNING: Frontend npm install failed. You can retry manually: cd frontend ^&^& npm install
    ) else (
        echo   Frontend setup complete.
    )
    popd
) else (
    echo [4/5] Skipping frontend setup ^(Node.js not installed^).
)

:: ---- Activate venv ----
echo.
echo [5/5] Activating virtual environment...
call "%~dp0backend\.venv\Scripts\activate.bat"

:: ---- Done ----
echo.
echo ============================================================
echo   Setup complete!
echo ============================================================
echo.
echo   To start the backend:
echo     cd backend
echo     .venv\Scripts\activate
echo     uvicorn app.main:app --reload --port 9100
echo.
echo   Or with uv (no activate needed):
echo     cd backend
echo     uv run uvicorn app.main:app --reload --port 9100
echo.
if %HAS_NODE% equ 1 (
    echo   To start the frontend:
    echo     cd frontend
    echo     npm run dev
    echo.
)
echo   CLI quick test:
echo     agenticeval --help
echo.
echo   Tip: Run '.venv\Scripts\activate' in backend\ to put
echo   agenticeval and uvicorn on your PATH in any new terminal.
echo.
