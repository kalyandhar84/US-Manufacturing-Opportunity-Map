#Requires -Version 7.0
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$SubscriptionId = if ($env:AZURE_SUBSCRIPTION_ID) { $env:AZURE_SUBSCRIPTION_ID } else { "3d05a5b5-8055-451d-9cd9-36016fd4b42b" }
$ResourceGroup = if ($env:RESOURCE_GROUP) { $env:RESOURCE_GROUP } else { "TMH-IT-POC" }
$WebAppName = if ($env:WEBAPP_NAME) { $env:WEBAPP_NAME } else { "us-opportunities" }

Write-Host "Setting subscription $SubscriptionId"
az account set --subscription $SubscriptionId

Write-Host "Deploying infrastructure to $ResourceGroup"
az deployment group create `
    --resource-group $ResourceGroup `
    --template-file ./infra/main.bicep `
    --parameters ./infra/main.parameters.json `
    --parameters webAppName=$WebAppName

Write-Host "Packaging application zip"
python ./scripts/package_app.py

$ZipPath = Join-Path $Root "dist/app.zip"
Write-Host "Zip-deploying $ZipPath to $WebAppName"
az webapp deploy `
    --resource-group $ResourceGroup `
    --name $WebAppName `
    --src-path $ZipPath `
    --type zip `
    --async false

$HostName = az webapp show --resource-group $ResourceGroup --name $WebAppName --query defaultHostName -o tsv
Write-Host "Deployed https://$HostName"
