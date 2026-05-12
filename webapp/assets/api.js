const FALLBACK_API_BASE_URL = "http://127.0.0.1:8001";


function normalizeBaseUrl(value) {
  return (value || FALLBACK_API_BASE_URL).replace(/\/+$/, "");
}


export function getWebAppConfig() {
  const globalConfig = window.__MULTI_RAG_WEBAPP_CONFIG__ || {};
  const bodyConfig = document.body.dataset.apiBaseUrl || "";
  const apiBaseUrl = normalizeBaseUrl(globalConfig.apiBaseUrl || bodyConfig);

  return {
    apiBaseUrl,
    docsUrl: `${apiBaseUrl}/docs`,
    healthUrl: `${apiBaseUrl}/health`,
    openApiUrl: `${apiBaseUrl}/openapi.json`,
  };
}


export async function fetchHealth() {
  const config = getWebAppConfig();
  const response = await fetch(config.healthUrl, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}.`);
  }

  return {
    ...config,
    payload: await response.json(),
  };
}
