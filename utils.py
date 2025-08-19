from urllib.parse import urlparse

def is_url(s):
    parsed = urlparse(s)
    return all([parsed.scheme in ("http", "https"), parsed.netloc])
