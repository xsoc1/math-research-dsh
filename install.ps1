# Installs the four skill bundles of this repository into the DSH user skill
# root ($DSH_HOME/skills) as directory junctions, so a `git pull` in the
# checkout hot-updates every skill (the DSH skill watcher follows the links).
#
# Usage (from the repository checkout):
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-Force]
#
# -Force replaces an existing real directory (a plain copy) at the target.
# Without it, existing non-junction targets are skipped with a warning.

param([switch]$Force)
$ErrorActionPreference = "Stop"

$dsh = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $HOME ".dsh" }
$repo = Join-Path $dsh "math-research-dsh"
$skillsRoot = Join-Path $dsh "skills"
$names = @("rigorous-open-math-research", "manage-math-research-program", "math-research-workflow", "lean-verify")

if ((Split-Path -Parent $PSScriptRoot) -ne $dsh) {
    Write-Output "note: checkout is not under `$DSH_HOME ($dsh); junctions point at $PSScriptRoot"
    $repo = Split-Path -Parent $PSScriptRoot
}
New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null

foreach ($s in $names) {
    $source = Join-Path $repo "skills\$s"
    $target = Join-Path $skillsRoot $s
    if (-not (Test-Path (Join-Path $source "SKILL.md"))) {
        throw "missing bundle source: $source"
    }
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.LinkType) {
            Write-Output "ok: already a junction: $target -> $($item.Target)"
            continue
        }
        if ($Force) {
            Remove-Item -Recurse -Force $target
        } else {
            Write-Output "warn: $target exists and is not a junction; re-run with -Force to replace"
            continue
        }
    }
    New-Item -ItemType Junction -Path $target -Target $source | Out-Null
    Write-Output "ok: junction created: $target -> $source"
}

Write-Output ""
Write-Output "Verify with: python (Join-Path $repo 'scripts\dsh-doctor.py')"
