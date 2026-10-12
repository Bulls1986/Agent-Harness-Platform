# Dev-only Windows host helper for keeping a systemd-based CubeSandbox WSL
# instance alive while physical Worker/Cube acceptance tests run.
#
# WSL systemd services alone do not guarantee the distro remains running.
# A Windows Task Scheduler action holds a real WSL process. No startup or
# logon trigger is registered; run it only when the Cube environment is used.
# .\scripts\dev_cube_wsl_keepalive.ps1 -Action Start
# .\scripts\dev_cube_wsl_keepalive.ps1 -Action Status
# .\scripts\dev_cube_wsl_keepalive.ps1 -Action Stop
[CmdletBinding()]
param(
    [ValidateSet('Start','Status','Stop')]
    [string] $Action = 'Status',
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string] $Distro = 'Ubuntu',
    [ValidateRange(1,24)]
    [int] $Hours = 12
)

$ErrorActionPreference = 'Stop'
$taskName = 'AgentHarness-Cube-WSL-OnDemand'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

switch ($Action) {
    'Status' {
        if ($null -eq $existing) {
            Write-Output 'CUBE_WSL_KEEPALIVE_STOPPED'
        } else {
            Write-Output "CUBE_WSL_KEEPALIVE_$($existing.State.ToString().ToUpperInvariant())"
            if ($null -ne $existing.Triggers -and @($existing.Triggers).Count -gt 0) {
                throw 'Unexpected automatic trigger on on-demand WSL keeper'
            }
        }
    }
    'Start' {
        if ($null -ne $existing -and $existing.State -eq 'Running') {
            Write-Output 'CUBE_WSL_KEEPALIVE_ALREADY_RUNNING'
            break
        }
        $seconds = $Hours * 3600
        $wsl = Join-Path $env:WINDIR 'System32\wsl.exe'
        $taskAction = New-ScheduledTaskAction -Execute $wsl -Argument "-d $Distro -u root -e sleep $seconds"
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        # No trigger is intentional: save memory when the lab is unused.
        Register-ScheduledTask -TaskName $taskName -Action $taskAction -Settings $settings -Description 'On-demand CubeSandbox WSL lifetime for Agent Harness tests' -Force | Out-Null
        Start-ScheduledTask -TaskName $taskName
        Start-Sleep -Seconds 2
        if ((Get-ScheduledTask -TaskName $taskName).State -ne 'Running') {
            throw 'WSL keeper did not reach Running; inspect Windows Task Scheduler'
        }
        Write-Output "CUBE_WSL_KEEPALIVE_RUNNING duration_hours=$Hours distro=$Distro"
    }
    'Stop' {
        if ($null -eq $existing) {
            Write-Output 'CUBE_WSL_KEEPALIVE_ALREADY_STOPPED'
            break
        }
        if ($existing.State -eq 'Running') {
            Stop-ScheduledTask -TaskName $taskName
        }
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Output 'CUBE_WSL_KEEPALIVE_STOPPED'
    }
}
