param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ScriptPath = Join-Path $PSScriptRoot "scripts\uninstall.ps1"
& $ScriptPath @Args
exit $LASTEXITCODE
