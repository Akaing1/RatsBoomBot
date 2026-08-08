$ErrorActionPreference = "Stop"

$PiUser = "rats-bot"
$PiHost = "192.168.68.54"
$SshKey = "$env:USERPROFILE\.ssh\ratsboombot_rpi"

$RemoteAppDir = "/opt/ratsboombot"
$RemoteDeployScript = "$RemoteAppDir/deploy/linux/deploy.sh"

Write-Host "[Deploy] Starting remote RatsBoomBot deployment."

ssh -i $SshKey "$PiUser@$PiHost" "cd $RemoteAppDir && $RemoteDeployScript"

if ($LASTEXITCODE -ne 0) {
    throw "[Deploy] Remote deployment failed with exit code $LASTEXITCODE."
}

Write-Host "[Deploy] Remote RatsBoomBot deployment completed successfully."