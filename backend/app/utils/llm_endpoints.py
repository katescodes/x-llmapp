from urllib.parse import urljoin


def normalize_base_url(u: str) -> str:
    return (u or "").strip().rstrip("/")


def normalize_endpoint_path(p: str) -> str:
    p = (p or "/v1/chat/completions").strip()
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/")


def build_endpoint_url(base_url: str, endpoint_path: str) -> str:
    base = normalize_base_url(base_url)
    path = normalize_endpoint_path(endpoint_path)
    return urljoin(base + "/", path.lstrip("/")).rstrip("/")

