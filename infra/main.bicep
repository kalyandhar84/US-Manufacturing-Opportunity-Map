param location string = resourceGroup().location
param webAppName string = 'us-opportunities'
param planName string = 'asp-us-opportunities'
param linuxFxVersion string = 'PYTHON|3.12'
param workerCount int = 1

var tags = {
  Application: 'AI, Azure Maps'
  Company: 'TMH'
  Environment: 'POC'
  'Technical Owner': 'Kalyan Dhar'
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  kind: 'linux'
  sku: {
    name: 'S1'
    tier: 'Standard'
    capacity: workerCount
  }
  properties: {
    reserved: true
  }
  tags: tags
}

resource web 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  tags: tags
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: linuxFxVersion
      alwaysOn: true
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
      http20Enabled: true
      appCommandLine: 'bash startup.sh'
      healthCheckPath: '/health'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'PORT'
          value: '8000'
        }
        {
          name: 'STREAMLIT_SERVER_HEADLESS'
          value: 'true'
        }
        {
          name: 'STREAMLIT_BROWSER_GATHERUSAGESTATS'
          value: 'false'
        }
        {
          name: 'PYTHONUNBUFFERED'
          value: '1'
        }
      ]
    }
  }
}

resource scmBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: web
  name: 'scm'
  properties: {
    allow: true
  }
}

resource ftpBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: web
  name: 'ftp'
  properties: {
    allow: true
  }
}

output webAppName string = web.name
output planName string = plan.name
output location string = location
output defaultHostName string = web.properties.defaultHostName
output webAppUrl string = 'https://${web.properties.defaultHostName}'
