$ErrorActionPreference = "SilentlyContinue"

function StartMenuShortcutPath {
    $programs = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs"
    $nested = Join-Path $programs "DeckArt Studio\DeckArt Studio.lnk"
    $flat = Join-Path $programs "DeckArt Studio.lnk"
    if (Test-Path $nested) { return $nested }
    if (Test-Path $flat) { return $flat }
    return $null
}

function Invoke-PinVerb([string]$shortcutPath) {
    $shell = New-Object -ComObject Shell.Application
    $folder = $shell.NameSpace((Split-Path -Parent $shortcutPath))
    if (-not $folder) { return }
    $item = $folder.ParseName((Split-Path -Leaf $shortcutPath))
    if (-not $item) { return }
    foreach ($verb in @($item.Verbs())) {
        $name = (($verb.Name) -replace "&", "").ToLowerInvariant()
        if ($name -like "*pin to taskbar*") {
            $verb.DoIt()
            return
        }
    }
}

$shortcut = StartMenuShortcutPath
if ($shortcut) {
    Invoke-PinVerb $shortcut
}
