"""
LLM client.

Wraps a single chat-completion call behind a Protocol. Two backends:

  - **LangChainClient**: Production. Uses LangChain's unified interface so
    you can swap providers (OpenAI, Azure OpenAI, Ollama, AWS Bedrock,
    HuggingFace, vLLM) without code changes. The provider is selected
    via the `LLM_PROVIDER` env var.

  - **StubLLMClient**: Dev/CI. Generates a structured response from the
    retrieved incidents using simple rules. Lets the pipeline run end-
    to-end without API keys or network access.

Both implement the `LLMClient` Protocol.

## Supported providers (via LangChain)

    LLM_PROVIDER=openai       + OPENAI_API_KEY
    LLM_PROVIDER=azure        + AZURE_OPENAI_*   env vars
    LLM_PROVIDER=ollama       + OLLAMA_BASE_URL  (default http://localhost:11434)
    LLM_PROVIDER=bedrock      + AWS_*            env vars
    LLM_PROVIDER=huggingface  + HUGGINGFACEHUB_API_TOKEN
    LLM_PROVIDER=vllm         + VLLM_ENDPOINT    (OpenAI-compatible)

For air-gapped / on-prem deployments: Ollama (local) and vLLM (self-hosted
GPU) require no external API calls.
"""

from __future__ import annotations

import json
import os
from typing import Optional, Protocol

from app.core import get_logger
from app.ml.root_cause_v2.types import RetrievedIncident

logger = get_logger(__name__)


class LLMClient(Protocol):
    """LLM client protocol."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str: ...


class LangChainClient:
    """Production client using LangChain's unified LLM interface.

    The provider is selected at construction time. Each provider uses its
    own LangChain integration package, loaded lazily so you only pay for
    the provider you actually use.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._provider = (provider or os.environ.get("LLM_PROVIDER") or "openai").lower()
        self._model = model or os.environ.get("LLM_MODEL")
        self._llm = self._build_llm()
        logger.info(
            "langchain_client_initialized",
            provider=self._provider,
            model=self._model,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        bound = self._llm.bind(max_tokens=max_tokens, temperature=temperature)
        response = bound.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        content = getattr(response, "content", None)
        if content is None:
            return str(response)
        if isinstance(content, list):
            # Some providers return a list of blocks
            text_parts = [
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            ]
            return "".join(text_parts).strip()
        return str(content).strip()

    def _build_llm(self):
        provider = self._provider
        model = self._model

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model or "gpt-4o-mini",
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL"),
            )

        if provider == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=model or os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            )

        if provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model or "llama3.1:8b",
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            )

        if provider == "bedrock":
            from langchain_aws import ChatBedrockConverse
            return ChatBedrockConverse(
                model_id=model or "anthropic.claude-3-5-sonnet-20241022-v2:0",
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
            )

        if provider == "huggingface":
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
            endpoint = HuggingFaceEndpoint(
                repo_id=model or "meta-llama/Llama-3.1-8B-Instruct",
                huggingfacehub_api_token=os.environ.get("HUGGINGFACEHUB_API_TOKEN"),
                task="text-generation",
            )
            return ChatHuggingFace(llm=endpoint)

        if provider == "vllm":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model or "meta-llama/Llama-3.1-8B-Instruct",
                base_url=os.environ.get("VLLM_ENDPOINT", "http://localhost:8000/v1"),
                api_key="not-needed",
            )

        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. "
            "Supported: openai, azure, ollama, bedrock, huggingface, vllm"
        )


class StubLLMClient:
    """Deterministic stub for dev / CI / air-gapped runs.

    Generates a JSON response by voting across retrieved incidents.
    Quality is bounded by what's in the knowledge base — sufficient to
    verify the pipeline wiring and to serve as a fallback when no LLM
    is configured.
    """

    def __init__(self) -> None:
        self._retrieved: list[RetrievedIncident] = []
        logger.warning(
            "using_stub_llm_client",
            note="set LLM_PROVIDER and credentials for production root cause analysis",
        )

    def set_retrieved(self, retrieved: list[RetrievedIncident]) -> None:
        self._retrieved = retrieved

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        retrieved = self._retrieved or []

        if not retrieved:
            return json.dumps({
                "probable_cause": "Unknown — no similar historical incidents found",
                "confidence": 0.2,
                "details": (
                    "Stub LLM produced a low-confidence response because no "
                    "historical incidents were retrieved. Configure LLM_PROVIDER "
                    "with credentials and seed the incident store for "
                    "production-quality output."
                ),
                "recommended_actions": [
                    "Manually triage this interface",
                    "Add this incident to the knowledge base once resolved",
                ],
                "referenced_incident_ids": [],
                "reasoning": "No retrieved incidents to reference.",
            })

        top = retrieved[0]
        cause_votes: dict[str, float] = {}
        for r in retrieved[:3]:
            cause_votes[r.incident.root_cause] = (
                cause_votes.get(r.incident.root_cause, 0.0) + r.similarity
            )
        best_cause = max(cause_votes.items(), key=lambda t: t[1])[0]
        confidence = min(0.85, top.similarity * 0.95)

        return json.dumps({
            "probable_cause": top.incident.root_cause_detail.split(".")[0]
            if top.incident.root_cause == best_cause
            else best_cause.replace("_", " ").title(),
            "confidence": round(confidence, 2),
            "details": (
                f"Retrieved {len(retrieved)} similar incidents, with the top match "
                f"having similarity {top.similarity:.2f}. The most consistent "
                f"root cause across top-K matches is `{best_cause}`."
            ),
            "recommended_actions": top.incident.actions_taken[:4],
            "referenced_incident_ids": [r.incident.incident_id for r in retrieved[:3]],
            "reasoning": (
                f"Stub LLM voted across top-3 retrieved incidents; "
                f"`{best_cause}` won by similarity-weighted vote."
            ),
        })


def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    """Factory — LangChain if a provider is configured, else stub.

    Detection order:
      1. If `LLM_PROVIDER` env var is set, try that provider.
      2. Else if `OPENAI_API_KEY` is set, default to OpenAI.
      3. Else return the stub.
    """
    provider = provider or os.environ.get("LLM_PROVIDER")

    if not provider and os.environ.get("OPENAI_API_KEY"):
        provider = "openai"

    if provider:
        try:
            return LangChainClient(provider=provider, model=model)
        except ImportError as exc:
            logger.warning(
                "langchain_provider_package_missing",
                provider=provider,
                error=str(exc),
                action=(
                    "install the relevant LangChain integration, e.g. "
                    "`poetry install --extras rca_v2_openai`"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "langchain_client_init_failed",
                provider=provider,
                error=str(exc),
            )

    return StubLLMClient()
