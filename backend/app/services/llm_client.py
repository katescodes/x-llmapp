import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
import httpx
from fastapi import HTTPException
import logging
from ..schemas.chat import Message
from ..schemas.llm_config import LLMModelStored
from ..services.llm_model_store import get_llm_store
from app.config import get_settings
from ..utils.llm_endpoints import (
    normalize_base_url,
    normalize_endpoint_path,
    build_endpoint_url,
)

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class LLMProfile:
    key: str
    display_name: str
    base_url: str
    model: str
    endpoint_path: str = "/v1/chat/completions"
    api_key: Optional[str] = None
    mock: bool = False


def get_llm_profiles() -> Dict[str, LLMProfile]:
    """
    从新的模型存储获取LLM配置，用于向后兼容。
    """
    store = get_llm_store()
    models = store.list_models()
    profiles: Dict[str, LLMProfile] = {}

    for model in models:
        profiles[model.id] = LLMProfile(
            key=model.id,
            display_name=model.name,
            base_url=model.base_url,
            model=model.model,
            endpoint_path=model.endpoint_path,
            api_key=model.api_key,
            mock=False,  # 新系统不再使用mock
        )

    # 如果没有配置，使用环境变量作为fallback
    if not profiles:
        llm_list = os.getenv("LLM_LIST", "local").split(",")
        for raw_key in llm_list:
            key = raw_key.strip()
            if not key:
                continue
            prefix = f"LLM_{key.upper()}_"
            base_url = os.getenv(prefix + "BASE_URL", settings.LOCAL_LLM_BASE_URL)
            model_name = os.getenv(prefix + "MODEL", settings.LOCAL_LLM_MODEL)
            display_name = os.getenv(prefix + "NAME", key)
            endpoint_path = os.getenv(
                prefix + "ENDPOINT_PATH", settings.LOCAL_LLM_ENDPOINT_PATH
            )
            api_key = os.getenv(prefix + "API_KEY") or settings.LOCAL_LLM_API_KEY
            mock_env = os.getenv(prefix + "MOCK", "")
            mock = settings.MOCK_LLM or mock_env.lower() == "true"

            profiles[key] = LLMProfile(
                key=key,
                display_name=display_name,
                base_url=normalize_base_url(base_url),
                model=model_name,
                endpoint_path=normalize_endpoint_path(endpoint_path),
                api_key=api_key,
                mock=mock,
            )

    return profiles


def get_default_llm_key() -> str:
    store = get_llm_store()
    default_model = store.get_default_model()
    return default_model.id if default_model else "local"


def select_llm_profile(llm_key: str | None) -> LLMProfile:
    profiles = get_llm_profiles()
    if llm_key and llm_key in profiles:
        return profiles[llm_key]
    default_key = get_default_llm_key()
    return profiles[default_key]


def llm_json(
    prompt: str,
    model_id: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """
    LLM JSON 输出专用函数（用于模板分析等结构化输出场景）
    
    Args:
        prompt: 提示词（应包含 JSON schema 要求）
        model_id: 模型 ID（可选，默认使用默认模型）
        temperature: 温度（默认 0.0，确保输出稳定）
        max_tokens: 最大 token 数
        
    Returns:
        解析后的 JSON 字典
        
    Raises:
        HTTPException: LLM 调用失败或 JSON 解析失败
    """
    import json
    import re
    
    logger.info(f"LLM JSON 调用: model={model_id}, temperature={temperature}")
    
    try:
        # 选择模型
        profile = select_llm_profile(model_id)
        
        if profile.mock:
            logger.warning("使用 MOCK 模式，返回空 JSON")
            return {}
        
        # 构建请求
        messages = [{"role": "user", "content": prompt}]
        
        # 调用 LLM
        full_url = build_endpoint_url(profile.base_url, profile.endpoint_path)
        
        headers = {"Content-Type": "application/json"}
        if profile.api_key:
            headers["Authorization"] = f"Bearer {profile.api_key}"
        
        payload = {
            "model": profile.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        with httpx.Client(timeout=300.0) as client:  # ✅ 优化：增加到300秒（5分钟）避免Stage 2超时
            response = client.post(full_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
        
        # 提取内容
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not content:
            raise HTTPException(status_code=500, detail="LLM 返回空内容")
        
        # 尝试解析 JSON
        # 1. 直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 2. 提取 JSON block（可能被包裹在 ```json ... ``` 中）
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 3. 提取任何 {...} 或 [...] 结构
        json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 解析失败
        logger.error(f"JSON 解析失败，原始内容: {content[:500]}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM 输出无法解析为 JSON: {content[:200]}"
        )
    
    except httpx.HTTPError as e:
        logger.error(f"LLM 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 调用失败: {str(e)}")
    
    except Exception as e:
        logger.error(f"LLM JSON 调用异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM JSON 调用异常: {str(e)}")


def get_llm_model_by_id(model_id: str) -> Optional[LLMModelStored]:
    """获取完整的LLM模型配置（包含敏感信息）"""
    store = get_llm_store()
    return store.get_model(model_id)


def get_default_llm_model() -> Optional[LLMModelStored]:
    """获取默认的LLM模型配置"""
    store = get_llm_store()
    return store.get_default_model()


def _apply_generation_overrides(
    payload: Dict[str, Any],
    overrides: Optional[Dict[str, Any]],
    request_kind: str | None = None,
) -> None:
    if not overrides:
        return
    targets = ("temperature", "max_tokens", "top_p")
    if request_kind and request_kind.startswith("ollama"):
        options = payload.setdefault("options", {})
        for key in targets:
            if key == "max_tokens":
                val = overrides.get(key)
                if val is not None:
                    # Ollama uses num_predict for token limit
                    options["num_predict"] = val
                continue
            val = overrides.get(key)
            if val is not None:
                options[key] = val
        return
    for key in targets:
        val = overrides.get(key)
        if val is not None:
            payload[key] = val


async def generate_answer_with_llm(
    system_prompt: str,
    user_message: str,
    history: List[Message],
    profile: LLMProfile,
    overrides: Optional[Dict[str, Any]] = None,
) -> str:
    """
    调用指定 LLMProfile 对应的 LLM。
    保留向后兼容性。
    """

    if profile.mock:
        history_text = "\n".join(f"{m.role}: {m.content}" for m in history)
        return (
            f"【MOCK 回答 · {profile.display_name}】\n"
            f"这是一个本地 LLM 的占位回答，用于前后端联调。\n\n"
            f"使用模型: {profile.model} @ {profile.base_url}\n\n"
            f"系统提示词（截断）：{system_prompt[:120]}...\n"
            f"用户问题：{user_message}\n\n"
            f"历史对话（截断）：\n{history_text[:400]}..."
        )

    url = build_endpoint_url(profile.base_url, profile.endpoint_path)
    payload = {
        "model": profile.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            *[m.model_dump() for m in history],
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
    }

    headers = {"Content-Type": "application/json"}
    token = profile.api_key or settings.LOCAL_LLM_API_KEY
    if token:
        headers["Authorization"] = f"Bearer {token}"

    _apply_generation_overrides(payload, overrides, None)

    try:
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=False) as client:  # ✅ 优化：增加到300秒（5分钟）
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (307, 308):
                location = resp.headers.get("Location") or ""
                detail = (
                    "LLM endpoint responded with a redirect."
                    " 请去掉尾部斜杠或改用 Location 指定的地址。"
                )
                if location:
                    detail += f" Location: {location}"
                raise HTTPException(status_code=502, detail=detail)
            resp.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.error("LLM request timed out profile=%s url=%s", profile.key, url)
        raise HTTPException(status_code=502, detail="LLM 请求超时，请检查模型服务") from exc
    except httpx.RequestError as exc:
        logger.error("LLM request error profile=%s url=%s error=%s", profile.key, url, exc)
        raise HTTPException(status_code=502, detail="LLM 请求失败，请检查模型服务") from exc

    answer, parsed = _parse_llm_response_text(resp.text)
    if answer:
        return answer
    return f"[LLM 返回格式异常] {parsed or resp.text[:400]}"


def _prepare_llm_request(
    system_prompt: str,
    user_message: str,
    history: List[Message],
    model: LLMModelStored,
    api_key: Optional[str],
    overrides: Optional[Dict[str, Any]],
):
    url = build_endpoint_url(model.base_url, model.endpoint_path)
    request_kind = _detect_llm_protocol(model.endpoint_path)
    messages = _build_conversation_messages(system_prompt, history, user_message)
    headers = {"Content-Type": "application/json"}
    token = api_key
    has_token = bool(token)
    if has_token:
        headers["Authorization"] = f"Bearer {token}"

    if model.extra_headers:
        for key, value in model.extra_headers.items():
            if key.lower() == "authorization" and "Authorization" in headers:
                continue
            headers[key] = value

    if request_kind == "ollama_chat":
        payload = _build_ollama_chat_payload(model, messages)
    elif request_kind == "ollama_generate":
        payload = _build_ollama_generate_payload(model, system_prompt, history, user_message)
    else:
        payload = _build_openai_payload(model, messages)

    _apply_generation_overrides(payload, overrides, request_kind)
    timeout = (model.timeout_ms or 120000) / 1000.0
    if timeout <= 0:
        timeout = 120.0

    return url, request_kind, headers, payload, timeout, messages, token, has_token


async def generate_answer_with_model(
    system_prompt: str,
    user_message: str,
    history: List[Message],
    model: LLMModelStored,
    api_key: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> str:
    """
    使用新的LLMModel配置调用LLM。
    """
    (
        url,
        request_kind,
        headers,
        payload,
        timeout,
        messages,
        token,
        has_token,
    ) = _prepare_llm_request(system_prompt, user_message, history, model, api_key, overrides)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            attempt = 0
            while True:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (307, 308):
                    location = resp.headers.get("Location") or ""
                    detail = (
                        "LLM endpoint responded with a redirect."
                        " 请去掉尾部斜杠或直接改用 Location 指定的地址。"
                    )
                    if location:
                        detail += f" Location: {location}"
                    raise HTTPException(status_code=502, detail=detail)
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response else "unknown"
                    msgs = payload.get("messages") or []
                    sys_len = len(msgs[0].get("content", "")) if msgs else 0
                    user_len = len(msgs[-1].get("content", "")) if msgs else 0
                    try:
                        import json

                        payload_preview = json.dumps(payload, ensure_ascii=False)[:1500]
                    except Exception:  # noqa: BLE001
                        payload_preview = "<unserializable>"

                    token_hint = ""
                    if token:
                        token_hint = f"{token[:3]}***{token[-3:]}" if len(token) >= 6 else "***"

                    logger.error(
                        (
                            "LLM HTTP error status=%s url=%s has_token=%s token_hint=%s "
                            "payload_keys=%s messages=%s sys_len=%s user_len=%s "
                            "payload_preview=%s"
                        ),
                        status,
                        url,
                        has_token,
                        token_hint,
                        list(payload.keys()),
                        len(msgs),
                        sys_len,
                        user_len,
                        payload_preview,
                    )
                    raise

                answer, parsed = _parse_llm_response_text(resp.text)

                if (
                    request_kind.startswith("ollama")
                    and _should_retry_ollama_load(parsed)
                ):
                    if attempt >= 1:
                        return "模型正在加载，请稍后再试"
                    attempt += 1
                    await asyncio.sleep(0.3)
                    continue

                if answer:
                    return _strip_think_tags(answer)
                return f"[LLM 返回格式异常] {parsed or resp.text[:400]}"
    except httpx.TimeoutException as exc:
        logger.error("LLM request timed out url=%s", url)
        raise HTTPException(status_code=502, detail="LLM 请求超时，请检查模型服务") from exc
    except httpx.RequestError as exc:
        logger.error("LLM request error url=%s error=%s", url, exc)
        raise HTTPException(status_code=502, detail="LLM 请求失败，请检查模型服务") from exc


async def stream_answer_with_model(
    system_prompt: str,
    user_message: str,
    history: List[Message],
    model: LLMModelStored,
    api_key: Optional[str],
    on_token: Callable[[str], Awaitable[None]],
    overrides: Optional[Dict[str, Any]] = None,
) -> str:
    (
        url,
        request_kind,
        headers,
        payload,
        timeout,
        _messages,
        token,
        _has_token,
    ) = _prepare_llm_request(system_prompt, user_message, history, model, api_key, overrides)

    if request_kind == "openai_chat":
        payload["stream"] = True
        headers.setdefault("Accept", "text/event-stream")
    else:
        payload["stream"] = True

    buffer: List[str] = []

    async def _consume_chunk(text: str) -> None:
        if text:
            buffer.append(text)
            await on_token(text)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response else "unknown"
                    logger.error(
                        "LLM stream HTTP error status=%s url=%s token=%s",
                        status,
                        url,
                        f"{token[:3]}***{token[-3:]}" if token else "none",
                    )
                    raise
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    cleaned = line.strip()
                    if not cleaned:
                        continue
                    if cleaned.startswith("data:"):
                        cleaned = cleaned[5:].strip()
                    if not cleaned or cleaned == "[DONE]":
                        continue
                    chunk_text: Optional[str] = None
                    try:
                        chunk_obj = json.loads(cleaned)
                    except json.JSONDecodeError:
                        chunk_text = cleaned
                    else:
                        chunk_text = _extract_text_from_chunk(chunk_obj)
                    if chunk_text:
                        await _consume_chunk(chunk_text)
                final_text = _strip_think_tags("".join(buffer))
                if final_text:
                    return final_text
                raise HTTPException(status_code=502, detail="LLM 流式返回为空")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM stream failed url=%s error=%s", url, exc, exc_info=True)
        answer = await generate_answer_with_model(
            system_prompt=system_prompt,
            user_message=user_message,
            history=history,
            model=model,
            api_key=api_key,
            overrides=overrides,
        )
        if answer:
            await on_token(answer)
        return answer


def _parse_llm_response_text(raw_text: str) -> Tuple[Optional[str], Optional[dict]]:
    """
    处理不同厂商返回格式：
    - OpenAI 兼容 choices/message
    - Ollama / LM Studio response 字段
    - OpenAI Streaming / delta / NDJSON
    - 其他返回 text / output / content
    """
    if not raw_text:
        return None, None
    raw_text = raw_text.strip()
    if not raw_text:
        return None, None

    try:
        data = json.loads(raw_text)
        text = _extract_text_from_chunk(data)
        return (text.strip() if text else text), data
    except json.JSONDecodeError:
        pass

    # 尝试逐行解析（NDJSON / SSE）
    fragments: List[str] = []
    last_obj: Optional[dict] = None
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        # SSE 可能以 "data: {...}" 开头
        if cleaned.startswith("data:"):
            cleaned = cleaned[5:].strip()
            if cleaned == "[DONE]":
                continue
        try:
            chunk = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        last_obj = chunk
        piece = _extract_text_from_chunk(chunk)
        if piece:
            fragments.append(piece)

    if fragments:
        return "".join(fragments), last_obj

    return None, last_obj


def _extract_text_from_chunk(chunk: dict) -> Optional[str]:
    if not isinstance(chunk, dict):
        return None

    # OpenAI-style choices
    choices = chunk.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            text = _extract_text_from_choice(choice)
            if text:
                return text

    # Anthropic / response API message field
    message = chunk.get("message")
    if isinstance(message, dict):
        text = _extract_text_from_message_content(message.get("content"))
        if text:
            return text

    # Ollama / LM Studio 字段
    response_text = chunk.get("response")
    if isinstance(response_text, str) and response_text.strip():
        return response_text

    # OpenAI responses API content 顶层
    content = chunk.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        fragments = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        joined = "".join(fragments).strip()
        if joined:
            return joined

    # 其他常见字段
    for key in ("text", "output", "result"):
        value = chunk.get(key)
        if isinstance(value, str) and value.strip():
            return value

    output_texts = chunk.get("output_texts")
    if isinstance(output_texts, list):
        joined = "\n".join(
            text for text in output_texts if isinstance(text, str) and text.strip()
        ).strip()
        if joined:
            return joined

    return None


def _detect_llm_protocol(endpoint_path: str | None) -> str:
    path = (endpoint_path or "").lower()
    if "/api/generate" in path:
        return "ollama_generate"
    if "/api/chat" in path:
        return "ollama_chat"
    return "openai_chat"


def _build_conversation_messages(
    system_prompt: str, history: List[Message], user_message: str
) -> List[dict]:
    messages: List[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_openai_payload(model: LLMModelStored, messages: List[dict]) -> dict:
    payload: dict = {
        "model": model.model,
        "messages": messages,
    }
    if model.temperature is not None:
        payload["temperature"] = model.temperature
    if model.max_tokens is not None:
        payload["max_tokens"] = model.max_tokens
    if model.top_p is not None:
        payload["top_p"] = model.top_p
    if model.presence_penalty is not None:
        payload["presence_penalty"] = model.presence_penalty
    if model.frequency_penalty is not None:
        payload["frequency_penalty"] = model.frequency_penalty
    return payload


def _build_ollama_chat_payload(model: LLMModelStored, messages: List[dict]) -> dict:
    payload: dict = {
        "model": model.model,
        "messages": messages,
        "stream": False,
    }
    options = _build_ollama_options(model)
    if options:
        payload["options"] = options
    return payload


def _build_ollama_generate_payload(
    model: LLMModelStored,
    system_prompt: str,
    history: List[Message],
    user_message: str,
) -> dict:
    lines: List[str] = []
    if system_prompt:
        lines.append(f"system: {system_prompt}")
    for msg in history:
        lines.append(f"{msg.role}: {msg.content}")
    lines.append(f"user: {user_message}")
    lines.append("assistant:")
    prompt = "\n".join(lines)
    payload: dict = {
        "model": model.model,
        "prompt": prompt,
        "stream": False,
    }
    options = _build_ollama_options(model)
    if options:
        payload["options"] = options
    return payload


def _build_ollama_options(model: LLMModelStored) -> dict:
    options: dict = {}
    if model.temperature is not None:
        options["temperature"] = model.temperature
    if model.max_tokens is not None:
        options["num_predict"] = model.max_tokens
    if model.top_p is not None:
        options["top_p"] = model.top_p
    # presence_penalty / frequency_penalty 暂无直接映射
    return options


def _should_retry_ollama_load(parsed: Optional[dict]) -> bool:
    return (
        isinstance(parsed, dict)
        and parsed.get("done_reason") == "load"
        and not (parsed.get("response") or "").strip()
    )


def _strip_think_tags(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return cleaned.strip()


def _extract_text_from_choice(choice: dict) -> Optional[str]:
    if not isinstance(choice, dict):
        return None

    # Streaming delta
    delta = choice.get("delta")
    if isinstance(delta, dict):
        text = _extract_text_from_message_content(delta.get("content"))
        if text:
            return text
        if isinstance(delta.get("text"), str) and delta["text"].strip():
            return delta["text"]

    message = choice.get("message")
    if isinstance(message, dict):
        text = _extract_text_from_message_content(message.get("content"))
        if text:
            return text

    if isinstance(choice.get("text"), str) and choice["text"].strip():
        return choice["text"]

    return None


def _extract_text_from_message_content(content) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments: List[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
            elif isinstance(item, dict):
                # OpenAI responses API
                if (
                    item.get("type") in ("output_text", "text")
                    and isinstance(item.get("text"), str)
                ):
                    fragments.append(item["text"])
                elif isinstance(item.get("value"), str):
                    fragments.append(item["value"])
        joined = "".join(fragments).strip()
        if joined:
            return joined
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text
    return None


class LLMClient:
    """LLM 客户端封装，提供统一的调用接口"""

    def __init__(self):
        self.store = get_llm_store()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        统一的聊天完成接口
        
        Args:
            messages: 消息列表，格式为 [{"role": "system/user/assistant", "content": "..."}]
            model: 模型ID，如果为None则使用默认模型
            temperature: 温度参数
            max_tokens: 最大token数
            top_p: top_p参数
            
        Returns:
            返回字典，格式为 {"content": "回复内容", "model": "使用的模型ID"}
        """
        # 获取模型配置
        if model:
            llm_model = self.store.get_model(model)
        else:
            llm_model = self.store.get_default_model()
        
        if not llm_model:
            raise ValueError(f"Model not found: {model or 'default'}")
        
        # 构造覆盖参数
        overrides: Dict[str, Any] = {}
        if temperature is not None:
            overrides["temperature"] = temperature
        if max_tokens is not None:
            overrides["max_tokens"] = max_tokens
        if top_p is not None:
            overrides["top_p"] = top_p
        
        # 解析消息
        system_prompt = ""
        user_message = ""
        history: List[Message] = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_message = content
            elif role == "assistant":
                # 将之前的user_message作为历史
                if user_message:
                    history.append(Message(role="user", content=user_message))
                    user_message = ""
                history.append(Message(role="assistant", content=content))
        
        # 如果没有提取到user_message，使用最后一条消息
        if not user_message and messages:
            last_msg = messages[-1]
            if last_msg.get("role") == "user":
                user_message = last_msg.get("content", "")
        
        # 调用底层函数
        answer = await generate_answer_with_model(
            system_prompt=system_prompt,
            user_message=user_message,
            history=history,
            model=llm_model,
            api_key=llm_model.api_key,
            overrides=overrides,
        )
        
        return {
            "content": answer,
            "model": llm_model.id,
        }


_llm_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取LLM客户端单例"""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
