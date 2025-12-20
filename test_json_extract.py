#!/usr/bin/env python3
import json

# 模拟LLM输出
text = """```json
{
  "data": {
    "base": {
      "projectName": "测试项目"
    }
  }
}
```"""

print("Original text:")
print(repr(text[:100]))
print()

text = text.strip()
print("After strip:")
print(repr(text[:100]))
print()

print("Contains '```json':", "```json" in text)

if "```json" in text:
    start_marker = text.find("```json")
    print(f"Found ```json at position: {start_marker}")
    
    start = start_marker + 7
    print(f"Start position after ```json: {start}")
    print(f"Char at start: {repr(text[start]) if start < len(text) else 'EOF'}")
    
    while start < len(text) and text[start] in (' ', '\n', '\r', '\t'):
        start += 1
    
    print(f"Start after skipping whitespace: {start}")
    print(f"Char at start: {repr(text[start:start+10])}")
    
    end = text.find("```", start)
    print(f"End position: {end}")
    
    if end > start:
        extracted = text[start:end].strip()
        print("\nExtracted JSON:")
        print(extracted[:200])
        
        try:
            result = json.loads(extracted)
            print("\nParsed successfully!")
            print(result)
        except Exception as e:
            print(f"\nFailed to parse: {e}")

