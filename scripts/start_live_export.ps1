<#
.SYNOPSIS
    Engine Exporter - Live export runner for the Local Mailbox Export Engine.

.DESCRIPTION
    Starts or triggers live incremental refresh of the Engine Exporter's local
    Knowledge Store.  Validates the environment, checks live status, enables
    live refresh, runs one cycle, or watches continuously.

.PARAMETER StatusOnly
    Show current live status and exit.

.PARAMETER Enable
    Enable live incremental refresh, show status, exit.

.PARAMETER Once
    Run one incremental refresh cycle, show status, exit.

.PARAMETER Watch
    Loop at the configured polling interval, showing status after each cycle.

.EXAMPLE
    .\scripts\start_live_export.ps1 -StatusOnly
    .\scripts\start_live_export.ps1 -Enable
    .\scripts\start_live_export.ps1 -Once
    .\scripts\start_live_export.ps1 -Watch
#>

param(
    [switch]$StatusOnly,
    [switch]$Enable,
    [switch]$Once,
    [switch]$Watch
)

# -- Repo path ------------------------------------------------------------
$RepoPath = Split-Path -Parent $PSScriptRoot
$ScriptsDir = $PSScriptRoot
Write-Host "Engine Exporter - Live Export Runner" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "Repo path: $RepoPath"
Write-Host ""

# -- Default mode ---------------------------------------------------------
if (-not $StatusOnly -and -not $Enable -and -not $Once -and -not $Watch) {
    Write-Host "No mode specified. Defaulting to -StatusOnly." -ForegroundColor Yellow
    $StatusOnly = $true
}

# -- Validators -----------------------------------------------------------
function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Msg)
    Write-Host "  [OK] $Msg" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Msg)
    Write-Host "  [FAIL] $Msg" -ForegroundColor Red
}

function Get-PythonExe {
    # Try .venv first, then system python
    $venvPython = Join-Path (Join-Path $RepoPath ".venv") "Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    $systemPython = (Get-Command "python" -ErrorAction SilentlyContinue).Source
    if ($systemPython) {
        return $systemPython
    }
    return $null
}

function Validate-Environment {
    Write-Header "Environment Validation"

    # Python
    $python = Get-PythonExe
    if (-not $python) {
        Write-Fail "Python executable not found.  Check .venv or system PATH."
        return $false
    }
    Write-Success "Python: $python"

    # Module import
    $test = & $python -c "import export_engine; print('ok')" 2>&1
    if ($LASTEXITCODE -ne 0 -or $test -ne 'ok') {
        Write-Fail "export_engine module cannot be imported."
        Write-Host "    $test"
        return $false
    }
    Write-Success "export_engine module importable"

    # CLI availability
    $cliTest = & $python -m export_engine.cli store-status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "export_engine.cli not available."
        return $false
    }
    Write-Success "export_engine.cli works"

    return $true
}

function Check-StorePaths {
    # Check that recall DB and live state exist
    $root = & $python -c "from export_engine.config import default_store_root; print(default_store_root())" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Cannot determine store root."
        return $false
    }
    $recallDb = Join-Path (Join-Path $root "index") "recall.sqlite"
    $liveState = Join-Path $root "live_state.json"

    Write-Host "  Store root: $root"
    Write-Host "  Recall DB:  $recallDb"
    Write-Host "  Live state: $liveState"

    if (-not (Test-Path $root)) {
        Write-Fail "Store root does not exist.  Run backfill first."
        return $false
    }
    if (-not (Test-Path $recallDb)) {
        Write-Fail "Recall DB missing.  Run store-build-index first."
        return $false
    }
    if (-not (Test-Path $liveState)) {
        Write-Warning "Live state file missing.  Run -Enable to initialise."
    }

    Write-Success "Store paths validated"
    return $true
}

# -- Mode implementations -------------------------------------------------

function Show-Status {
    Write-Header "Current Live Status"
    & $python -m export_engine.cli store-live-status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "store-live-status: OK"
    } else {
        Write-Fail "store-live-status returned $LASTEXITCODE"
    }
}

function Enable-Live {
    Write-Header "Enabling Live Refresh"
    & $python -m export_engine.cli store-live-enable 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "Live refresh enabled."
        Write-Host ""
        Show-Status
    } else {
        Write-Fail "store-live-enable returned $LASTEXITCODE"
    }
}

function Run-Once {
    Write-Header "Running One Incremental Refresh Cycle"
    & $python -m export_engine.cli store-live-refresh-once 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "Refresh cycle completed."
        Write-Host ""
        Show-Status
    } else {
        Write-Fail "store-live-refresh-once returned $LASTEXITCODE"
    }
}

function Run-Watch {
    Write-Header "Watch Mode - Continuous Live Refresh"
    Write-Host "  Press Ctrl+C to stop."
    Write-Host ""

    while ($true) {
        Write-Header ("Cycle: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
        & $python -m export_engine.cli store-live-refresh-once 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Refresh cycle failed - check logs."
        } else {
            Write-Success "Cycle complete."
        }

        # Read polling interval from live state
        $root = & $python -c "from export_engine.config import default_store_root; print(default_store_root())" 2>&1
        $liveStatePath = Join-Path $root "live_state.json"
        $interval = 5
        if (Test-Path $liveStatePath) {
            try {
                $state = Get-Content $liveStatePath | ConvertFrom-Json
                $interval = $state.defaultPollingIntervalMinutes
                if (-not $interval) { $interval = 5 }
            } catch {}
        }
        Write-Host "  Next cycle in $interval minute(s).  Press Ctrl+C to stop."
        Write-Host ""
        Start-Sleep -Seconds ($interval * 60)
    }
}

# -- Main -----------------------------------------------------------------

$python = Get-PythonExe
if (-not $python) {
    Write-Fail "Python executable not found.  Set up .venv first."
    exit 1
}
Write-Host "Using Python: $python"
Write-Host ""

if (-not (Validate-Environment)) {
    Write-Fail "Environment validation failed."
    exit 1
}

if ($StatusOnly -or $Once -or $Enable) {
    if (-not (Check-StorePaths)) {
        Write-Fail "Store path validation failed."
        exit 1
    }
}

Write-Host ""

if ($StatusOnly) {
    Show-Status
    Write-Host ""
    Write-Host "Operator hints:" -ForegroundColor Yellow
    Write-Host "  .\scripts\start_live_export.ps1 -Enable    -- enable live refresh"
    Write-Host "  .\scripts\start_live_export.ps1 -Once      -- run one refresh cycle"
    Write-Host "  .\scripts\start_live_export.ps1 -Watch     -- continuous watch mode"
} elseif ($Enable) {
    Enable-Live
} elseif ($Once) {
    Run-Once
} elseif ($Watch) {
    Run-Watch
}

Write-Host ""
Write-Host "Command: $($MyInvocation.Line)" -ForegroundColor DarkGray
Write-Host "Completed at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
