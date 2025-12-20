from __future__ import annotations

import logging

from app.services.embedding import http_embedding_client as emb_client


def _reset_probe_flags():
    emb_client._EMB_PROBED = False  # type: ignore[attr-defined]


def test_embedding_probe_logs_once_for_openai_like_response(caplog):
    _reset_probe_flags()
    payload = {
        "object": "list",
        "model": "mock-model",
        "data": [
            {
                "embedding": [0.1, 0.2, 0.3],
                "index": 0,
            }
        ],
        "usage": {"prompt_tokens": 1, "total_tokens": 2},
    }

    with caplog.at_level(logging.INFO):
        emb_client._maybe_probe_response(payload)  # type: ignore[attr-defined]
        emb_client._maybe_probe_response(payload)  # second call should be ignored

    probe_logs = [record for record in caplog.records if "Embedding probe" in record.message]
    assert len(probe_logs) == 1
    assert "0.1" not in probe_logs[0].message


def test_embedding_probe_reports_sparse_keys(caplog):
    _reset_probe_flags()
    payload = {
        "results": [
            {
                "dense": [0.5, 0.1],
                "sparse_embedding": {"indices": [1, 2], "values": [0.2, 0.3]},
                "lexical_weights": {"token_a": 0.1, "token_b": 0.4},
            }
        ],
        "provider": "mock-provider",
    }

    with caplog.at_level(logging.INFO):
        emb_client._maybe_probe_response(payload)  # type: ignore[attr-defined]

    probe_logs = [record for record in caplog.records if "Embedding probe" in record.message]
    assert probe_logs, "expected probe log"
    message = probe_logs[0].message
    assert "sparse_embedding" in message
    assert "lexical_weights" in message
    assert "0.2" not in message  # ensure values themselves are not logged

