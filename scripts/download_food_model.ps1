[CmdletBinding()]
param(
    [string]$Repo = "HL123456789123/xjtu-visagent2026--",
    [string]$Tag = "food-model-v1.0",
    [string]$AssetName = "visagent-food-model-v1-yolo11s.zip",
    [string]$ModelDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) "models\\food")
)

$ErrorActionPreference = "Stop"

$expectedModelHash = "680accafc8c22854b37e959106c37a44b3e8c42b4d260d7f3c4681021c2a31cd"
$expectedClassesHash = "8bd06c89afe18fbb6bf7d64d44b51f84f8199a80678e63123f35c09fd6c9913b"
$expectedModelBytes = 19194771L
$expectedClassesBytes = 640L
$repoRoot = Split-Path -Parent $PSScriptRoot
$trackedClasses = Join-Path $repoRoot "backend\\scripts\\food_model\\classes.yaml"

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required to download the model release."
}
if (-not (Test-Path -LiteralPath $trackedClasses -PathType Leaf)) {
    throw "Tracked classes file is missing: $trackedClasses"
}
if ((Get-Item -LiteralPath $trackedClasses).Length -ne $expectedClassesBytes -or
    (Get-Sha256 $trackedClasses) -ne $expectedClassesHash) {
    throw "Tracked classes.yaml does not match the frozen V1 model pair. Refusing download."
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("visagent-food-model-" + [guid]::NewGuid().ToString("N"))
$downloadDirectory = Join-Path $tempRoot "download"
$extractDirectory = Join-Path $tempRoot "extract"
New-Item -ItemType Directory -Force -Path $downloadDirectory, $extractDirectory | Out-Null

try {
    gh release download $Tag --repo $Repo --pattern $AssetName --pattern "SHA256SUMS.txt" --dir $downloadDirectory

    $archive = Join-Path $downloadDirectory $AssetName
    $sums = Join-Path $downloadDirectory "SHA256SUMS.txt"
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or -not (Test-Path -LiteralPath $sums -PathType Leaf)) {
        throw "Release is missing the model archive or SHA256SUMS.txt."
    }
    $sumLine = Get-Content -LiteralPath $sums | Where-Object { $_ -match ("(?:\\*|\\s)" + [regex]::Escape($AssetName) + "$") } | Select-Object -First 1
    if (-not $sumLine) { throw "SHA256SUMS.txt has no entry for $AssetName." }
    $expectedArchiveHash = ($sumLine -split "\\s+")[0].ToLowerInvariant()
    if ((Get-Sha256 $archive) -ne $expectedArchiveHash) { throw "Release archive SHA-256 mismatch." }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace("\\", "/")
            if ([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith("/") -or $name -match "(^|/)\\.\\.(/|$)" -or $name -match "^[A-Za-z]:") {
                throw "Unsafe archive entry: $name"
            }
        }
    } finally {
        $zip.Dispose()
    }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($archive, $extractDirectory)

    $weights = @(Get-ChildItem -LiteralPath $extractDirectory -Recurse -File -Filter "best.pt")
    $classes = @(Get-ChildItem -LiteralPath $extractDirectory -Recurse -File -Filter "classes.yaml")
    if ($weights.Count -ne 1 -or $classes.Count -ne 1) { throw "Release archive must contain exactly one best.pt and one classes.yaml." }
    if ($weights[0].Length -ne $expectedModelBytes -or (Get-Sha256 $weights[0].FullName) -ne $expectedModelHash) { throw "best.pt checksum or size mismatch." }
    if ($classes[0].Length -ne $expectedClassesBytes -or (Get-Sha256 $classes[0].FullName) -ne $expectedClassesHash) { throw "Release classes.yaml checksum or size mismatch." }
    if (-not [System.Linq.Enumerable]::SequenceEqual([System.IO.File]::ReadAllBytes($classes[0].FullName), [System.IO.File]::ReadAllBytes($trackedClasses))) {
        throw "Release classes.yaml differs from the tracked frozen classes file."
    }

    New-Item -ItemType Directory -Force -Path $ModelDirectory | Out-Null
    $target = Join-Path $ModelDirectory "best.pt"
    if (Test-Path -LiteralPath $target) {
        if ((Get-Sha256 $target) -ne $expectedModelHash) { throw "Existing local best.pt has a different checksum; refusing overwrite." }
        Write-Output "Existing verified best.pt retained: $target"
    } else {
        Copy-Item -LiteralPath $weights[0].FullName -Destination $target
        Write-Output "Verified best.pt installed: $target"
    }
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
