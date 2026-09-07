<#
.SYNOPSIS
    Builds DeckArt Studio into a shareable Windows folder + zip, and tests the result.

.DESCRIPTION
    1. Creates/updates the .venv and installs runtime + build requirements.
    2. Runs the self-test from source (fails fast if the app is broken).
    3. Generates the icon and runs PyInstaller (packaging\DeckArtStudio.spec).
    4. Runs the self-test again, this time inside the frozen EXE.
    5. Zips dist\DeckArtStudio into dist\DeckArtStudio-<version>-win64.zip.

.PARAMETER Online
    Also exercise Scryfall in the self-tests (needs internet).
.PARAMETER Launch
    Start the built EXE when everything passed.
.PARAMETER SkipTests
    Skip both self-test runs (not recommended before sending a build out).

.EXAMPLE
    .\packaging\build_exe.ps1 -Online -Launch
#>
param(
    [switch]$Online,
    [switch]$Launch,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$DistFolder = Join-Path $ProjectRoot "dist\DeckArtStudio"
$env:PYTHONIOENCODING = "utf-8"

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }

function Ensure-Venv {
    if (-not (Test-Path $Python)) {
        Step "Creating virtual environment"
        $bootstrap = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" } else { "python" }
        Invoke-Expression "$bootstrap -m venv `"$Venv`""
    }
    Step "Installing requirements"
    & $Python -m pip install --quiet --upgrade pip
    & $Python -m pip install --quiet -r (Join-Path $ProjectRoot "requirements.txt") -r (Join-Path $ProjectRoot "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

function Build-PlateTextures {
    Step "Building plate textures"
    & $Python -m deckart_studio.tools.build_plate_textures
    if ($LASTEXITCODE -ne 0) { throw "Plate texture build failed" }
}

function Read-Version {
    return (& $Python -c "from deckart_studio.version import APP_VERSION; print(APP_VERSION)").Trim()
}

function Selftest-Arguments {
    $arguments = @("--selftest")
    if ($Online) { $arguments += "--online" }
    return $arguments
}

function Run-SourceSelftest {
    Step "Self-test from source"
    & $Python -m deckart_studio @(Selftest-Arguments)
    if ($LASTEXITCODE -ne 0) { throw "Source self-test failed" }
}

function Build-Icon {
    Step "Generating icon"
    & $Python -m deckart_studio.tools.make_icon (Join-Path $ProjectRoot "packaging\deckart.ico")
    if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }
}

function Close-RunningApp {
    $running = Get-Process -Name "DeckArtStudio", "DeckArtStudio-debug" -ErrorAction SilentlyContinue
    if (-not $running) { return }
    Step "Asking the running DeckArt Studio to close (it will prompt if a deck has unsaved changes)"
    $running | ForEach-Object { $_.CloseMainWindow() | Out-Null }
    $running | Wait-Process -Timeout 20 -ErrorAction SilentlyContinue
    if (Get-Process -Name "DeckArtStudio", "DeckArtStudio-debug" -ErrorAction SilentlyContinue) {
        throw "DeckArt Studio is still running (unsaved changes?). Close it, then re-run the build."
    }
}

function Run-PyInstaller {
    Step "Running PyInstaller"
    Close-RunningApp
    if (Test-Path $DistFolder) { Remove-Item $DistFolder -Recurse -Force }
    & $Python -m PyInstaller --noconfirm --clean --log-level WARN --distpath (Join-Path $ProjectRoot "dist") `
        --workpath (Join-Path $ProjectRoot "build\pyinstaller") (Join-Path $ProjectRoot "packaging\DeckArtStudio.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
}

function Run-FrozenSelftest {
    Step "Self-test inside the frozen EXE"
    $debugExe = Join-Path $DistFolder "DeckArtStudio-debug.exe"
    $arguments = (Selftest-Arguments) -join " "
    $output = cmd /c "`"$debugExe`" $arguments 2>&1" | Out-String
    Write-Host $output
    if ($LASTEXITCODE -ne 0 -or $output -notmatch "SELFTEST OK") { throw "Frozen self-test failed" }
}

function Copy-ReadMe {
    Copy-Item (Join-Path $ProjectRoot "packaging\README-DeckArtStudio.txt") (Join-Path $DistFolder "README.txt") -Force
}

function Create-Zip($version) {
    Step "Zipping"
    $zip = Join-Path $ProjectRoot "dist\DeckArtStudio-$version-win64.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path $DistFolder -DestinationPath $zip -CompressionLevel Optimal
    $sizeMb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host "`nBuilt: $zip ($sizeMb MB)" -ForegroundColor Green
    Write-Host "Folder: $DistFolder" -ForegroundColor Green
}

Push-Location $ProjectRoot
try {
    Ensure-Venv
    $version = Read-Version
    Write-Host "DeckArt Studio $version" -ForegroundColor Yellow
    Build-PlateTextures
    if (-not $SkipTests) { Run-SourceSelftest }
    Build-Icon
    Run-PyInstaller
    if (-not $SkipTests) { Run-FrozenSelftest }
    Copy-ReadMe
    Create-Zip $version
    if ($Launch) { Start-Process (Join-Path $DistFolder "DeckArtStudio.exe") }
}
finally {
    Pop-Location
}
