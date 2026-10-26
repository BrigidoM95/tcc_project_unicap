$ErrorActionPreference = 'Stop'
$raizProjeto = Split-Path -Parent $PSScriptRoot
$pastaWeb = Join-Path $raizProjeto 'tcc-web'
$pythonProjeto = Join-Path $pastaWeb 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProjeto)) { $pythonProjeto = Join-Path $raizProjeto '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $pythonProjeto)) { throw 'Execute INSTALAR_WINDOWS.cmd primeiro.' }
Set-Location -LiteralPath $pastaWeb
& $pythonProjeto manage.py migrate --check
if ($LASTEXITCODE -ne 0) { throw 'Há migrações pendentes. Faça backup e execute manage.py migrate.' }
$operacaoProjeto = Start-Process -FilePath $pythonProjeto -ArgumentList @('manage.py','processar_operacao','--continuo') -WorkingDirectory $pastaWeb -WindowStyle Hidden -PassThru
try {
    Write-Host 'Painel: http://127.0.0.1:8000/ — operação automática iniciada.'
    & $pythonProjeto manage.py runserver 127.0.0.1:8000
} finally {
    if (-not $operacaoProjeto.HasExited) { Stop-Process -Id $operacaoProjeto.Id }
}
