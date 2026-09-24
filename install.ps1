param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ScriptPath = Join-Path $PSScriptRoot "scripts\install.ps1"
& $ScriptPath @Args
exit $LASTEXITCODE
