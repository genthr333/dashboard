// Public configuration only. Never put API tokens or credentials here.
window.OBS_CONFIG = {
  mode: 'simulation',
  portalOrigin: 'https://monitor.example.org',
  summaryEndpoint: '/api/v1/overview', // Served by backend/server.py; same-origin endpoint.
  sources: {
    signoz: {name:'SigNoz', url:'https://signoz.example.org', path:'/dashboard'},
    kuma: {name:'Uptime Kuma', url:'https://kuma.example.org', path:'/status/production'},
    matomo: {name:'Matomo', url:'https://matomo.example.org', path:'/index.php?module=CoreHome&action=index&idSite=1&period=day&date=today'},
    superset: {name:'Superset', url:'https://superset.example.org', path:'/superset/dashboard/executive/'}
  }
};
