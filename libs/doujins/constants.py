from base64 import b64decode as atob

BASE_URL = atob("aHR0cHM6Ly9uaGVudGFpLm5ldA==").decode("utf-8")
CDN_URL = atob("aHR0cHM6Ly9pNy5uaGVudGFpLm5ldA==").decode("utf-8")
