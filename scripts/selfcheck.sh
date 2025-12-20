#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/7] docker compose up -d --build"
docker compose up -d --build

echo "[2/7] 检查 /api/settings/app"
curl -fsS http://localhost:9001/api/settings/app >/tmp/app-settings.json
echo "✓ settings 可访问，写入 /tmp/app-settings.json"

echo "[3/7] 检查 Embedding 服务可用性"
python - <<'PY'
import json
from pathlib import Path
from urllib import request, parse, error

cfg_path = Path("./data/app_settings.json")
if not cfg_path.exists():
    print("✗ 缺少 ./data/app_settings.json，无法读取 embedding_config")
    raise SystemExit(1)

settings = json.loads(cfg_path.read_text(encoding="utf-8"))
emb = settings.get("embedding_config") or {}
base = (emb.get("base_url") or "").strip()
endpoint = (emb.get("endpoint_path") or "/v1/embeddings").strip()
model = (emb.get("model") or "bge-m3").strip()
output_sparse = emb.get("output_sparse", True)
output_dense = emb.get("output_dense", True)
sparse_format = emb.get("sparse_format", "indices_values")

if not base:
    print("✗ embedding_config.base_url 未配置")
    raise SystemExit(1)

full_url = base.rstrip("/") + "/" + endpoint.lstrip("/")
payload = {"model": model, "input": ["ping"]}
if output_sparse:
    payload.update(
        {
            "texts": ["ping"],
            "output_dense": output_dense,
            "output_sparse": output_sparse,
            "sparse_format": sparse_format,
        }
    )

req = request.Request(
    full_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
api_key = (emb.get("api_key") or "").strip()
if api_key:
    req.add_header("Authorization", f"Bearer {api_key}")

try:
    with request.urlopen(req, timeout=15) as resp:
        resp.read()
except Exception as exc:
    print(f"✗ embedding 服务不可达: {exc}")
    raise SystemExit(1)

print("✓ embedding 服务连通性正常")
PY

echo "[4/7] 发送一次离线聊天请求"
curl -fsS -X POST http://localhost:9001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"自检连通性测试","history":[],"search_mode":"off"}' >/tmp/chat-response.json
SESSION_ID=$(python - <<'PY'
import json
from pathlib import Path
data = json.load(Path("/tmp/chat-response.json").open())
print(data.get("session_id",""))
PY
)
if [[ -z "$SESSION_ID" || "$SESSION_ID" == "None" ]]; then
  echo "✗ 无法从聊天响应中解析 session_id"
  exit 1
fi
echo "✓ 会话 ID: $SESSION_ID"
curl -fsS http://localhost:9001/api/history/sessions/"$SESSION_ID" >/tmp/session-response.json
echo "✓ 会话详情已写入 /tmp/session-response.json"

if [[ -n "${GOOGLE_CSE_API_KEY:-}" && -n "${GOOGLE_CSE_CX:-}" ]]; then
echo "[5/7] 触发一次联网聊天测试"
  curl -fsS -X POST http://localhost:9001/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message":"最新 AI 新闻","history":[],"search_mode":"smart"}' >/tmp/chat-search-response.json
  echo "✓ 联网聊天响应已保存到 /tmp/chat-search-response.json"
else
  echo "[5/7] 跳过联网聊天测试（未检测到 GOOGLE_CSE_API_KEY/CX 环境变量）"
fi

echo "[6/7] 自检知识库 CRUD + 导入"
KB_NAME="selfcheck-$(date +%s)"
SELF_TOKEN="SELFTEST-${KB_NAME}"
KB_JSON=$(curl -fsS -X POST http://localhost:9001/api/kb \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$KB_NAME\",\"description\":\"Selfcheck KB\"}")
KB_ID=$(python - <<'PY'
import json,sys
data=json.loads(sys.argv[1])
print(data.get("id",""))
PY
"$KB_JSON")
if [[ -z "$KB_ID" || "$KB_ID" == "None" ]]; then
  echo "✗ 知识库创建失败"
  exit 1
fi
printf "Self-check KB generated at %s with token %s\n" "$(date)" "$SELF_TOKEN" >/tmp/kb-demo.txt
curl -fsS -X POST http://localhost:9001/api/kb/"$KB_ID"/import \
  -F "files=@/tmp/kb-demo.txt" >/tmp/kb-import.json
curl -fsS http://localhost:9001/api/kb/"$KB_ID"/docs >/tmp/kb-docs.json
DOC_ID=$(python - <<'PY'
import json,sys
with open("/tmp/kb-docs.json","r",encoding="utf-8") as fh:
    data=json.load(fh)
print(data[0]["id"] if data else "")
PY
)
if [[ -z "$DOC_ID" ]]; then
  echo "✗ 无法解析文档 ID"
  exit 1
fi

curl -fsS -X POST http://localhost:9001/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"请复述标记 $SELF_TOKEN\",\"history\":[],\"search_mode\":\"off\",\"kb_ids\":[\"$KB_ID\"]}" \
  >/tmp/kb-chat-before.json
HIT=$(python - <<'PY'
import json,sys
data=json.load(open("/tmp/kb-chat-before.json"))
print(len(data.get("sources", [])))
PY
)
if [[ "$HIT" -eq 0 ]]; then
  echo "✗ 导入文档后未命中引用"
  exit 1
fi

curl -fsS -X DELETE http://localhost:9001/api/kb/"$KB_ID"/docs/"$DOC_ID" >/dev/null
curl -fsS -X POST http://localhost:9001/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"请复述标记 $SELF_TOKEN\",\"history\":[],\"search_mode\":\"off\",\"kb_ids\":[\"$KB_ID\"]}" \
  >/tmp/kb-chat-after.json
MISS=$(python - <<'PY'
import json,sys
data=json.load(open("/tmp/kb-chat-after.json"))
print(len(data.get("sources", [])))
PY
)
if [[ "$MISS" -ne 0 ]]; then
  echo "✗ 删除文档后仍返回引用"
  exit 1
fi

curl -fsS -X DELETE http://localhost:9001/api/kb/"$KB_ID" >/dev/null
docker compose exec -T backend env KB_TARGET="$KB_ID" python - <<'PY'
from pymilvus import MilvusClient
import os
kb_id = os.environ.get("KB_TARGET")
client = MilvusClient(uri="/app/data/milvus.db")
if client.has_collection("chunks_v1"):
    res = client.query(
        collection_name="chunks_v1",
        filter=f'kb_id == "{kb_id}"',
        output_fields=["chunk_id"],
    )
    assert not res, f"Milvus 仍存在 {len(res)} 条 kb={kb_id} 数据"
PY
echo "✓ 知识库导入/检索/删除流程通过"

echo "[7/7] 重启 docker 并检查关键数据文件"
docker compose restart backend frontend
sleep 5

files=(
  "./data/app_settings.json"
  "./data/search_usage.json"
  "./data/milvus.db"
  "./data/app.sqlite"
  "./data/index.sqlite"
)
missing=0
for f in "${files[@]}"; do
  if [[ -f "$f" ]]; then
    echo "✓ $f 存在"
  else
    echo "✗ 缺少 $f"
    missing=1
  fi
done

if [[ $missing -eq 0 ]]; then
  echo "自检完成 ✅"
else
  echo "自检未通过，请检查缺失文件 ❌"
  exit 1
fi

