from app.utils.llm_endpoints import build_endpoint_url


def test_build_endpoint_url_removes_trailing_slashes():
    base_url = "https://xai.yglinker.com:50443/511/"
    endpoint_path = "/v1/chat/completions/"
    result = build_endpoint_url(base_url, endpoint_path)
    assert result == "https://xai.yglinker.com:50443/511/v1/chat/completions"

