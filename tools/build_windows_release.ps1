[CmdletBinding()]
param(
    [string]$ExpectedVersion = "0.5.0",
    [switch]$KeepBuildEnvironment,
    [switch]$SkipFrozenStartupSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "This release builder must run on Windows."
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$venv = Join-Path $root ".venv-release"
$dist = Join-Path $root "dist"
$build = Join-Path $root "build"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE: $FilePath $($Arguments -join ' ')"
    }
}

function Assert-Exists {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required release path is missing: $Path"
    }
}

Write-Host "== PS5 FFPFSC Renamer local Windows release build =="
Write-Host "Repository: $root"
Write-Host "Expected version: $ExpectedVersion"

if (Test-Path -LiteralPath $venv) {
    Remove-Item -LiteralPath $venv -Recurse -Force
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $pyLauncher) {
    Invoke-Checked $pyLauncher.Source "-3.11" "-m" "venv" $venv
} else {
    $pythonCommand = Get-Command python -ErrorAction Stop
    $pythonVersion = (& $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    if ($pythonVersion -ne "3.11") {
        throw "Python 3.11 is required. Found Python $pythonVersion."
    }
    Invoke-Checked $pythonCommand.Source "-m" "venv" $venv
}

$python = Join-Path $venv "Scripts\python.exe"
$pyinstaller = Join-Path $venv "Scripts\pyinstaller.exe"
Assert-Exists $python

try {
    Invoke-Checked $python "-m" "pip" "install" "--upgrade" "pip"
    Invoke-Checked $python "-m" "pip" "install" "-e" ".[dev]" "mkpfs==0.0.9" "pyinstaller" "pillow"

    $version = (& $python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read project version."
    }
    if ($version -ne $ExpectedVersion) {
        throw "Refusing to build version '$version'. Expected exactly '$ExpectedVersion'."
    }

    Write-Host "== Compile source =="
    Invoke-Checked $python "-m" "compileall" "-q" "src" "tools"

    Write-Host "== Run full pytest suite =="
    Invoke-Checked $python "-m" "pytest" "-q"

    Write-Host "== Generate official application artwork =="
    Invoke-Checked $python "tools/generate_app_icon.py"

    if (Test-Path -LiteralPath $build) {
        Remove-Item -LiteralPath $build -Recurse -Force
    }
    if (Test-Path -LiteralPath $dist) {
        Remove-Item -LiteralPath $dist -Recurse -Force
    }

    Write-Host "== Build bundled MkPFS helper from current source =="
    Invoke-Checked $pyinstaller `
        "--noconfirm" `
        "--clean" `
        "--onefile" `
        "--console" `
        "--name" "mkpfs-helper" `
        "--collect-all" "mkpfs" `
        "--hidden-import" "cryptography" `
        "--hidden-import" "zlib_ng" `
        "tools/mkpfs_helper.py"

    $helper = Join-Path $dist "mkpfs-helper.exe"
    Assert-Exists $helper
    Invoke-Checked $helper "--help"

    Write-Host "== Smoke-test frozen helper low-memory metadata command =="
    $smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ps5-ffpfsc-release-smoke-" + [guid]::NewGuid().ToString("N"))
    $smokeSource = Join-Path $smokeRoot "source"
    $smokeSceSys = Join-Path $smokeSource "sce_sys"
    $smokeImage = Join-Path $smokeRoot "synthetic.ffpfsc"
    $smokeOutput = Join-Path $smokeRoot "param-output.json"
    New-Item -ItemType Directory -Force -Path $smokeSceSys | Out-Null
    try {
        $smokeJson = '{"titleId":"PPSA01285","localizedParameters":{"defaultLanguage":"en-US","en-US":{"titleName":"Release Smoke Test"}}}'
        Set-Content -LiteralPath (Join-Path $smokeSceSys "param.json") -Value $smokeJson -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $smokeSource "unrelated.bin") -Value "unrelated payload" -Encoding ASCII

        Invoke-Checked $python "-m" "mkpfs" "pack" "folder" $smokeSource $smokeImage "--no-adjust-output-file-extension" "--skip-verification"
        Invoke-Checked $helper "read-param-json" $smokeImage $smokeOutput
        Assert-Exists $smokeOutput
        $smokeMetadata = Get-Content -LiteralPath $smokeOutput -Raw | ConvertFrom-Json
        if ($smokeMetadata.titleId -ne "PPSA01285") {
            throw "Frozen helper smoke test returned unexpected metadata."
        }
    } finally {
        if (Test-Path -LiteralPath $smokeRoot) {
            Remove-Item -LiteralPath $smokeRoot -Recurse -Force
        }
    }

    Write-Host "== Build application from current source =="
    Invoke-Checked $pyinstaller `
        "--noconfirm" `
        "--clean" `
        "--onedir" `
        "--windowed" `
        "--name" "PS5-FFPFSC-Renamer" `
        "--icon" "assets/app-icon.ico" `
        "--paths" "src" `
        "--add-data" "assets/brand;assets/brand" `
        "--collect-submodules" "send2trash" `
        "tools/app_entry.py"

    $builtApp = Join-Path $dist "PS5-FFPFSC-Renamer"
    Assert-Exists (Join-Path $builtApp "PS5-FFPFSC-Renamer.exe")
    Assert-Exists (Join-Path $builtApp "_internal")

    $packageName = "PS5-FFPFSC-Renamer-v$version-Windows-x64"
    $packageDir = Join-Path $dist $packageName
    if (Test-Path -LiteralPath $packageDir) {
        Remove-Item -LiteralPath $packageDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
    Copy-Item -Path (Join-Path $builtApp "*") -Destination $packageDir -Recurse -Force
    Copy-Item -LiteralPath $helper -Destination (Join-Path $packageDir "mkpfs-helper.exe") -Force
    Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $packageDir -Force
    Copy-Item -LiteralPath (Join-Path $root "CHANGELOG.md") -Destination $packageDir -Force
    Copy-Item -LiteralPath (Join-Path $root "LICENSE") -Destination $packageDir -Force
    Copy-Item -LiteralPath (Join-Path $root "THIRD_PARTY_NOTICES.md") -Destination $packageDir -Force

    $thirdParty = Join-Path $packageDir "source\third-party"
    New-Item -ItemType Directory -Force -Path $thirdParty | Out-Null
    Invoke-Checked $python "-m" "pip" "download" "--no-deps" "--no-binary=:all:" "mkpfs==0.0.9" "-d" $thirdParty
    Copy-Item -LiteralPath (Join-Path $root "tools\mkpfs_helper.py") -Destination (Join-Path $thirdParty "mkpfs_helper.py") -Force

    Write-Host "== Validate release layout =="
    $required = @(
        "PS5-FFPFSC-Renamer.exe",
        "mkpfs-helper.exe",
        "_internal",
        "_internal\assets\brand",
        "source\third-party",
        "source\third-party\mkpfs_helper.py",
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md"
    )
    foreach ($relative in $required) {
        Assert-Exists (Join-Path $packageDir $relative)
    }

    if (Test-Path -LiteralPath (Join-Path $packageDir "assets")) {
        throw "Unexpected redundant assets directory in package root."
    }
    if (Test-Path -LiteralPath (Join-Path $packageDir "app-icon.png")) {
        throw "Unexpected redundant app-icon.png in package root."
    }

    $mkpfsSources = @(Get-ChildItem -LiteralPath $thirdParty -File | Where-Object { $_.Name -match '^mkpfs-0\.0\.9\.(tar\.gz|zip)$' })
    if ($mkpfsSources.Count -lt 1) {
        throw "MkPFS 0.0.9 source distribution is missing from source/third-party."
    }

    if (-not $SkipFrozenStartupSmoke) {
        Write-Host "== Smoke-test frozen desktop startup =="
        $oldLocalAppData = $env:LOCALAPPDATA
        $smokeProfile = Join-Path ([System.IO.Path]::GetTempPath()) ("ps5-ffpfsc-app-profile-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $smokeProfile | Out-Null
        $appProcess = $null
        try {
            $env:LOCALAPPDATA = $smokeProfile
            $appProcess = Start-Process -FilePath (Join-Path $packageDir "PS5-FFPFSC-Renamer.exe") -PassThru
            Start-Sleep -Seconds 6
            $appProcess.Refresh()
            if ($appProcess.HasExited) {
                throw "Frozen desktop exited during startup smoke test with code $($appProcess.ExitCode)."
            }
        } finally {
            if ($null -ne $appProcess -and -not $appProcess.HasExited) {
                Stop-Process -Id $appProcess.Id -Force
            }
            $env:LOCALAPPDATA = $oldLocalAppData
            if (Test-Path -LiteralPath $smokeProfile) {
                Remove-Item -LiteralPath $smokeProfile -Recurse -Force
            }
        }
    }

    $archive = Join-Path $dist ($packageName + ".zip")
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }

    Write-Host "== Create versioned ZIP with versioned top-level folder =="
    Compress-Archive -Path $packageDir -DestinationPath $archive -CompressionLevel Optimal
    Assert-Exists $archive

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $prefix = $packageName + "/"
        $badEntries = @($zip.Entries | Where-Object { -not $_.FullName.StartsWith($prefix, [System.StringComparison]::Ordinal) })
        if ($badEntries.Count -gt 0) {
            throw "ZIP contains entries outside the expected top-level '$packageName/' folder."
        }
    } finally {
        $zip.Dispose()
    }

    $hash = Get-FileHash -LiteralPath $archive -Algorithm SHA256
    Write-Host ""
    Write-Host "BUILD OK"
    Write-Host "Package folder: $packageDir"
    Write-Host "ZIP: $archive"
    Write-Host "SHA256: $($hash.Hash)"
    Write-Host ""
    Write-Host "No Git tag or GitHub release was created or modified."
} finally {
    if (-not $KeepBuildEnvironment -and (Test-Path -LiteralPath $venv)) {
        Remove-Item -LiteralPath $venv -Recurse -Force
    }
}
