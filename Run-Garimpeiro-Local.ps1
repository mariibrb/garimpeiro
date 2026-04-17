#Requires -Version 5.0
<#
.SYNOPSIS
  Atalho para o Garimpeiro local (CLI). Repassa todos os argumentos a garimpeiro_cli.py.
.EXAMPLE
  .\Run-Garimpeiro-Local.ps1 -Entrada "D:\LoteCliente" -Saida "D:\Export" -Cnpj "12345678000199" -Modo pasta
.EXAMPLE
  .\Run-Garimpeiro-Local.ps1 -Entrada "D:\Lote" -Saida "D:\Out" -Cnpj "12345678000199" -Modo sped -Codigo "578"
#>
param(
    [Parameter(Mandatory = $true)][string]$Entrada,
    [Parameter(Mandatory = $true)][string]$Saida,
    [Parameter(Mandatory = $true)][string]$Cnpj,
    [ValidateSet("pasta", "sped")][string]$Modo = "pasta",
    [string]$Codigo = "",
    [string]$Stem = ""
)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cli = Join-Path $root "garimpeiro_cli.py"
$args = @(
    "--entrada", $Entrada,
    "--saida", $Saida,
    "--cnpj", $Cnpj,
    "--modo", $Modo
)
if ($Codigo) { $args += @("--codigo", $Codigo) }
if ($Stem) { $args += @("--stem", $Stem) }
& py -3 -u $cli @args
exit $LASTEXITCODE
