# Start every StockPulse service. Each gets its own window so the logs stay
# readable and any one of them can be restarted without touching the others.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

docker compose up -d

$windows = @(
    @{ Title = "django"; Dir = "$root\backend";    Cmd = ".\venv\Scripts\Activate.ps1; python manage.py runserver" },
    @{ Title = "celery"; Dir = "$root\backend";    Cmd = ".\venv\Scripts\Activate.ps1; celery -A config worker --loglevel=info --pool=solo" },
    @{ Title = "ws";     Dir = "$root\ws-service"; Cmd = "npm run dev" }
)

foreach ($w in $windows) {
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "`$Host.UI.RawUI.WindowTitle = '$($w.Title)'; cd '$($w.Dir)'; $($w.Cmd)"
    )
}

Write-Host "postgres + redis in docker; django, celery and ws in their own windows."
