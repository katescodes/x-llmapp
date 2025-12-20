#!/usr/bin/env bash
set -euo pipefail

echo "Testing SearXNG JSON endpoint connectivity..."
for i in $(seq 1 5); do
  query="test${i}"
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://searxng:8080/search?q=${query}&format=json&language=zh-CN&safesearch=1")
  echo "Request ${i} (${query}) -> ${code}"
done

