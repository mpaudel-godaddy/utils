<# 
Compare all DLL versions between .\deploy and .\rollback (recursively)

Run from your chg101 folder:
  .\Compare-Dlls.ps1

Optional:
  .\Compare-Dlls.ps1 -DeployPath .\deploy -RollbackPath .\rollback -ReportCsv .\dll-compare.csv
#>

[CmdletBinding()]
param(
  [string]$DeployPath   = ".\deploy",
  [string]$RollbackPath = ".\rollback",
  [string]$ReportCsv
)

function Resolve-NormalizedPath {
  param([string]$Path)
  $item = Resolve-Path -LiteralPath $Path -ErrorAction Stop
  return ($item.ProviderPath.TrimEnd('\','/'))
}

function Get-Version {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return $null }

  # Try managed (.NET) assembly version first
  try {
    $asm = [Reflection.AssemblyName]::GetAssemblyName($Path).Version
    if ($asm) { return $asm }
  } catch { }

  # Fall back to Win32 file version metadata
  try {
    $vi = (Get-Item -LiteralPath $Path).VersionInfo
    foreach ($raw in @($vi.FileVersion, $vi.ProductVersion)) {
      if ($raw) {
        try { return [version]$raw } catch { return $raw }
      }
    }
  } catch { }

  return $null
}

function Build-DllIndex {
  <#
    Returns a hashtable keyed by lowercased relative path -> object { RelativePath, FullPath, Version }
    If the same relative path appears multiple times, keeps the highest version it can parse.
  #>
  param([string]$Root)

  $index = @{}
  if (-not (Test-Path -LiteralPath $Root)) { return $index }

  Get-ChildItem -LiteralPath $Root -Recurse -File -Filter *.dll | ForEach-Object {
    $rel = $_.FullName.Substring($Root.Length).TrimStart('\','/')
    $key = $rel.ToLowerInvariant()
    $ver = Get-Version -Path $_.FullName

    if (-not $index.ContainsKey($key)) {
      $index[$key] = [pscustomobject]@{
        RelativePath = $rel
        FullPath     = $_.FullName
        Version      = $ver
      }
    } else {
      # If both are [version], keep the higher one; otherwise keep the first non-null
      $cur = $index[$key]
      if ($ver -is [version] -and $cur.Version -is [version]) {
        if ($ver -gt $cur.Version) { $index[$key] = $cur | Select-Object *; $index[$key].Version = $ver; $index[$key].FullPath = $_.FullName }
      } elseif ($null -eq $cur.Version -and $ver) {
        $index[$key] = $cur | Select-Object *; $index[$key].Version = $ver; $index[$key].FullPath = $_.FullName
      }
    }
  }

  return $index
}

function Compare-VersionValues {
  param($DeployVer, $RollbackVer)

  if ($null -eq $RollbackVer -and $null -eq $DeployVer) { return "Missing" }
  if ($null -eq $RollbackVer) { return "MissingInRollback" }
  if ($null -eq $DeployVer)   { return "MissingInDeploy" }

  $bothAreVersion = ($DeployVer -is [version]) -and ($RollbackVer -is [version])
  if ($bothAreVersion) {
    if ($DeployVer -gt $RollbackVer) { return "NewerInDeploy" }
    elseif ($DeployVer -lt $RollbackVer) { return "OlderInDeploy" }
    else { return "Same" }
  } else {
    if ([string]::Equals([string]$DeployVer, [string]$RollbackVer, [System.StringComparison]::OrdinalIgnoreCase)) { "Same" }
    else { "Different" }
  }
}

try {
  $deployRoot   = Resolve-NormalizedPath -Path $DeployPath
  $rollbackRoot = Resolve-NormalizedPath -Path $RollbackPath
} catch {
  Write-Error "Failed to resolve paths. $_"; exit 1
}

if (-not (Test-Path -LiteralPath $deployRoot))   { Write-Error "Deploy path not found: $deployRoot";     exit 1 }
if (-not (Test-Path -LiteralPath $rollbackRoot)) { Write-Error "Rollback path not found: $rollbackRoot"; exit 1 }

$deployIndex   = Build-DllIndex -Root $deployRoot
$rollbackIndex = Build-DllIndex -Root $rollbackRoot

# Union of keys (all relative paths that exist on either side)
$allKeys = @($deployIndex.Keys + $rollbackIndex.Keys) | Select-Object -Unique

$rows = foreach ($k in ($allKeys | Sort-Object)) {
  $d = $deployIndex[$k]
  $r = $rollbackIndex[$k]

  $rel = if ($d) { $d.RelativePath } elseif ($r) { $r.RelativePath } else { $k }

  $deployVer   = if ($d) { $d.Version } else { $null }
  $rollbackVer = if ($r) { $r.Version } else { $null }
  $status      = Compare-VersionValues -DeployVer $deployVer -RollbackVer $rollbackVer

  [pscustomobject]@{
    FileName         = [IO.Path]::GetFileName($rel)
    RelativePath     = $rel
    DeployVersion    = $deployVer
    RollbackVersion  = $rollbackVer
    Status           = $status
    DeployFullPath   = if ($d) { $d.FullPath } else { $null }
    RollbackFullPath = if ($r) { $r.FullPath } else { $null }
  }
}

# Pretty console output (concise one-line per DLL)
$rows | Sort-Object RelativePath | ForEach-Object {
  $dv = if ($_.DeployVersion) { "$($_.DeployVersion)" } else { "missing" }
  $rv = if ($_.RollbackVersion) { "$($_.RollbackVersion)" } else { "missing" }
  Write-Host ("{0} -> deploy {1}, rollback {2} ({3})" -f $_.RelativePath, $dv, $rv, $_.Status)
}

# Optional CSV export
if ($ReportCsv) {
  try {
    $rows | Sort-Object RelativePath | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $ReportCsv
    Write-Host "CSV report written to: $ReportCsv"
  } catch {
    Write-Warning "Failed to write CSV: $_"
  }
}