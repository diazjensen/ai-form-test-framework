"""
Lightweight LLM wrapper using LangChain or direct HTTP calls (Ollama / OpenAI).

Provider order (LLM_PROVIDER=auto, default):
  1. LangChain / Direct Ollama  -- if local Ollama responds at OLLAMA_URL (default http://localhost:11434)
  2. LangChain / Direct OpenAI  -- if OPENAI_API_KEY environment variable is set
  3. None                       -- caller uses deterministic template / heuristic fallback

complete(prompt, system=...) returns (text, provider_name) and NEVER raises:
on any network/key failure it returns (None, "none") so test execution is never disrupted.
"""
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "15"))


def _ollama_up() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=1.0).status_code == 200
    except Exception:
        return False


def _call_langchain_openai(prompt: str, system: str, max_tokens: int) -> str:
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        chat = ChatOpenAI(model=OPENAI_MODEL, max_tokens=max_tokens, temperature=0.2)
        resp = chat.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        return resp.content.strip()
    except Exception:
        # Fallback to direct HTTP OpenAI call
        return _call_openai_direct(prompt, system, max_tokens)


def _call_openai_direct(prompt: str, system: str, max_tokens: int) -> str:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={
            "model": OPENAI_MODEL,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_ollama(prompt: str, system: str) -> str:
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def active_provider() -> str:
    choice = os.environ.get("LLM_PROVIDER", "auto").lower()
    if choice == "none":
        return "none"
    if choice in ("ollama", "langchain-ollama"):
        return "ollama" if _ollama_up() else "none"
    if choice in ("openai", "langchain", "langchain-openai"):
        return "openai" if os.environ.get("OPENAI_API_KEY") else "none"
    if _ollama_up():
        return "ollama"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "none"


def complete(prompt: str, system: str = "You are a concise QA assistant.", max_tokens: int = 400):
    provider = active_provider()
    try:
        if provider == "ollama":
            return _call_ollama(prompt, system), "ollama"
        if provider == "openai":
            return _call_langchain_openai(prompt, system, max_tokens), "openai (langchain/direct)"
    except Exception as e:
        print(f"[llm_client] Provider '{provider}' call failed ({e}); falling back.")
    return None, "none"
