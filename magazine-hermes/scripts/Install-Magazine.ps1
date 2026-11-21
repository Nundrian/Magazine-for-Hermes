param(
    [string]$Container = 'hermes',
    [ValidateSet('install','uninstall','rollback')][string]$Operation = 'install',
    [string]$Backup = ''
)
$ErrorActionPreference = 'Stop'
$MagazineSource = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$MagazineStage = '/tmp/magazine-package-' + [Guid]::NewGuid().ToString('N')
& docker exec $Container mkdir -p $MagazineStage
if ($LASTEXITCODE -ne 0) { throw 'Cannot create isolated package staging directory' }
& docker cp ($MagazineSource + '/.') ($Container + ':' + $MagazineStage)
if ($LASTEXITCODE -ne 0) { throw 'Package copy failed' }
$MagazineArgs = @('exec', $Container, '/opt/hermes/.venv/bin/python', ($MagazineStage + '/scripts/install.py'), $MagazineStage, '--operation', $Operation)
if ($Operation -eq 'rollback') {
    if (-not $Backup) { throw 'Supply the exact backup directory printed by the installation' }
    $MagazineArgs += @('--backup', $Backup)
}
& docker @MagazineArgs
if ($LASTEXITCODE -ne 0) { throw 'Magazine installation refused or failed; inspect the diagnostic above' }
Write-Host 'Reopen the Hermes dashboard. Refresh plugin discovery or restart only the dashboard service if this image requires it. Nothing starts inference.'
