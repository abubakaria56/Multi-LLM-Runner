import asyncio
import json
import logging
import os
import re
import traceback
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Type, TypeVar

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# Define replacement classes for LlamaIndex classes
class MessageRole:
    """Replacement for LlamaIndex MessageRole"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


@dataclass
class ChatMessage:
    """Replacement for LlamaIndex ChatMessage"""

    role: str
    content: str

    def __str__(self) -> str:
        return self.role


@dataclass
class CompletionResponse:
    """Replacement for LlamaIndex CompletionResponse"""

    text: str

    def __init__(self, text: str):
        self.text = text


@dataclass
class LLMMetadata:
    """Replacement for LlamaIndex LLMMetadata"""

    context_window: int
    num_output: int
    model_name: str
    is_chat_model: bool


@dataclass
class ChatResponse:
    """Replacement for LlamaIndex ChatResponse"""

    message: ChatMessage
    raw: Dict[str, Any]


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ModelParams:
    temperature: float = 0.7
    top_p: float = 1.0
    top_k: int = 40
    max_tokens: int = 10000


def _should_retry_on_error(response: Dict[str, Any]) -> bool:
    """Check if we should retry based on the error response"""
    if "error" not in response:
        return False

    error_str = str(response.get("error", "")).lower()
    retryable_errors = [
        "504",
        "429",
        "timeout",
        "gateway",
        "server",
        "temporary",
        "unavailable",
        "invalid response",  # Our custom validation errors
        "no choices found",
        "no content in message",
        "invalid response format",
    ]
    return any(error in error_str for error in retryable_errors)


class KongLLM:
    """Unified LLM client for Kong LLM Gateway API"""

    model_data = {
        "deepseek-r1-0528": "DeepSeek",
        "deepseek-r1": "DeepSeek",
        "claude-3-7-sonnet-20250219": "Anthropic",
        "gemini-2.5-flash-preview-05-20": "Gemini",
        "gemini-2.5-pro-preview-03-25": "Gemini",
        "o3": "OpenAI",
        "gpt-4.1": "OpenAI",
        "gpt-4o": "OpenAI",
        "llama-v3p1-405b-instruct-long": "Llama",
        "us.amazon.nova-premier-v1:0": "Amazon",
    }

    model_name_map = {
        "DeepSeek R1 New": "deepseek-r1-0528",
        "DeepSeek R1": "deepseek-r1",
        "Sonnet 3.7": "claude-3-7-sonnet-20250219",
        "GPT 4o": "gpt-4o",
        "Nova Premier": "us.amazon.nova-premier-v1:0",
        "Gemini 2.5 Flash": "gemini-2.5-flash-preview-05-20",
        "Gemini 2.5 Pro": "gemini-2.5-pro-preview-03-25",
    }

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro-preview-03-25",
        temperature: float = 0.7,
        max_tokens: int = 10000,
        **kwargs,
    ):
        self.api_key = os.environ.get("KONG_API_KEY", "your_kong_api_key")
        self.gw_key = os.environ.get("API_GATEWAY_KEY", "your_gw_key")
        self.auth_token = os.environ.get("AUTH_TOKEN", "your_auth_token")
        assert self.api_key and self.gw_key and self.auth_token, (
            "All API keys must be set"
        )
        assert model_name in self.model_name_map, f"Unsupported model: {model_name}"
        self.model_name = self.model_name_map.get(model_name, model_name)
        self.provider = self.model_data.get(self.model_name, "Unknown")
        self.base_url = os.environ.get(
            "KONG_API_BASE_URL", "https://kong.xyv.com/api/llm-gateway"
        )
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Set up headers for API requests
        self.headers = {
            "x-api-key": self.api_key,
            "x-api-gw-key": self.gw_key,
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
        }

        # Create async client
        self.async_client = httpx.AsyncClient(
            headers=self.headers,
            timeout=httpx.Timeout(
                600.0, read=600.0, write=60.0
            ),  # Fixed timeout values
        )

        logger.info(
            f"Initialized KongLLM with model: {model_name}, provider: {self.provider}"
        )

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.aclose()

    async def aclose(self):
        """Close the async client"""
        await self.async_client.aclose()
        logger.info("Closed KongLLM async client")

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata"""
        return LLMMetadata(
            context_window=100000,  # Adjust based on your model's context window
            num_output=self.max_tokens,
            model_name=self.model_name,
            is_chat_model=True,
        )

    @property
    def model(self) -> str:
        """Return model name for compatibility"""
        return self.model_name

    async def run_async(
        self,
        model_name: str,
        provider: str,
        messages: List[Message],
        params: Optional[ModelParams] = None,
        images: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Make an async API request to the LLM Gateway"""
        if params is None:
            params = ModelParams()
        if images is None:
            images = []

        messages_dict = [asdict(msg) for msg in messages]
        payload = {
            "modelName": model_name,
            "provider": provider,
            "messages": messages_dict,
            "params": asdict(params),
            "images": images,
        }

        logger.debug(
            f"Making request to {self.base_url} with model: {model_name}, provider: {provider}"
        )

        try:
            response = await self.async_client.post(self.base_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Handle HTTP status errors (4xx, 5xx)
            error_response = {
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "status_code": e.response.status_code,
                "stack_trace": traceback.format_exc(),
            }
            logger.error(f"HTTP Error {e.response.status_code}: {e.response.text}")
            return error_response
        except httpx.RequestError as e:
            # Handle network/connection errors
            error_response = {
                "error": f"Request failed: {str(e)}",
                "status_code": None,
                "stack_trace": traceback.format_exc(),
            }
            logger.error(f"Request failed: {str(e)}")
            return error_response
        except Exception as e:
            # Handle any other unexpected errors
            error_response = {
                "error": f"Unexpected error: {str(e)}",
                "status_code": None,
                "stack_trace": traceback.format_exc(),
            }
            logger.error(f"Unexpected error: {str(e)}")
            return error_response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_result(_should_retry_on_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
    )
    async def _make_request_with_retry(
        self, messages: List[Message], params: ModelParams
    ) -> Dict[str, Any]:
        """Make API request with retry logic using tenacity library"""
        logger.debug(f"Making request attempt to {self.base_url}")

        response = await self.run_async(
            model_name=self.model_name,
            provider=self.provider,
            messages=messages,
            params=params,
        )

        logger.debug(f"Response received: {response}")

        # If there's an explicit error in the response, return it for retry logic
        if "error" in response:
            logger.warning(f"Request failed with error: {response.get('error')}")
            return response

        # Validate response structure - if invalid, treat as error for retry
        try:
            choices = response.get("choices", [])
            if not choices or not isinstance(choices, list):
                logger.warning(
                    "Invalid response: no choices found or choices is not a list"
                )
                return {
                    "error": "Invalid response: no choices found or choices is not a list"
                }

            if len(choices) == 0:
                logger.warning("Invalid response: empty choices list")
                return {"error": "Invalid response: empty choices list"}

            message = choices[0].get("message", {})
            if not message or not isinstance(message, dict):
                logger.warning(
                    "Invalid response: no message found or message is not a dict"
                )
                return {
                    "error": "Invalid response: no message found or message is not a dict"
                }

            content = message.get("content", "")
            if not content or not isinstance(content, str):
                logger.warning(
                    "Invalid response: no content in message or content is not a string"
                )
                return {
                    "error": "Invalid response: no content in message or content is not a string"
                }

            # Response is valid
            logger.info("Request successful")
            return response

        except (KeyError, IndexError, AttributeError, TypeError) as e:
            logger.warning(f"Invalid response format: {e}")
            return {"error": f"Invalid response format: {e}"}

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Complete a prompt asynchronously"""
        messages = [Message(role="user", content=prompt)]
        params = ModelParams(
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        logger.info(
            f"Starting completion with temperature: {params.temperature}, max_tokens: {params.max_tokens}"
        )
        response = await self._make_request_with_retry(messages, params)

        if "error" in response:
            logger.error(f"LLM Gateway Error: {response['error']}")
            raise ValueError(f"LLM Gateway Error: {response['error']}")

        # Response is already validated in _make_request_with_retry
        content = self._clean_response_text(
            response["choices"][0]["message"]["content"]
        )
        logger.info(f"Successfully completed prompt, response length: {len(content)}")
        return CompletionResponse(text=content)

    def _clean_response_text(self, text: str) -> str:
        """Remove <think> tags and extract only the actual response content"""
        if not text:
            return ""

        # Remove <think>...</think> blocks (including multiline)
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        # Clean up extra whitespace and newlines
        cleaned = cleaned.strip()

        # Remove leading/trailing newlines
        while cleaned.startswith("\n"):
            cleaned = cleaned[1:]
        while cleaned.endswith("\n"):
            cleaned = cleaned[:-1]

        return cleaned

    async def ajson_complete(
        self,
        base_prompt: str,
        model: Type[T],
        max_retry: int = 3,
        **kwargs: Any,
    ) -> T:
        """Complete a prompt and return parsed JSON response"""
        json_prompt = f"""
{base_prompt}

IMPORTANT: Respond with ONLY valid JSON. Do not include any explanations, markdown formatting, or additional text. Your response must be a single, raw JSON object.

The JSON should match this schema:
{json.dumps(model.model_json_schema(mode="serialization"), indent=2)}
"""

        kwargs.setdefault("temperature", 0.1)
        logger.info(f"Starting JSON completion with {max_retry} max retries")
        response_text = ""

        for current_try in range(max_retry):
            try:
                # Call the async version
                response = await self.acomplete(json_prompt, **kwargs)
                response_text = response.text.strip()

                # Try to extract JSON from response
                json_match = re.search(r"{{.*}}", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(0)

                # Parse and validate JSON
                data = json.loads(response_text)
                parsed_model = model.model_validate(data)
                logger.info(
                    f"Successfully parsed JSON response on attempt {current_try + 1}"
                )
                return parsed_model

            except json.JSONDecodeError as e:
                if current_try < max_retry - 1:
                    json_prompt += f"\n\nThe response you provided: {response_text} is not in a valid JSON format. Please ensure your response is a valid JSON object that matches the schema provided above."
                    logger.warning(
                        f"JSON parsing failed (attempt {current_try + 1}/{max_retry}): {e}"
                    )
                    continue
                else:
                    logger.error(
                        f"Failed to parse JSON after {max_retry} retries. Last response: {response_text}"
                    )
                    raise ValueError(
                        f"Failed to parse JSON after {max_retry} retries. Last response: {response_text}"
                    )
            except Exception as e:
                if current_try < max_retry - 1:
                    logger.warning(
                        f"Error (attempt {current_try + 1}/{max_retry}): {e}"
                    )
                    continue
                else:
                    logger.error(
                        f"Failed to get valid response after {max_retry} retries: {e}"
                    )
                    raise ValueError(
                        f"Failed to get valid response after {max_retry} retries: {e}"
                    )

        # This should never be reached, but just in case
        logger.error(f"Failed to get valid JSON after {max_retry} retries")
        raise ValueError(f"Failed to get valid JSON after {max_retry} retries")

    async def chat_complete(
        self,
        messages: List[Message],
        **kwargs: Any,
    ) -> Message:
        """Complete a a chat conversation"""
        params = ModelParams(
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        logger.info(f"Starting chat completion with {len(messages)} messages")
        response = await self._make_request_with_retry(messages, params)

        if "error" in response:
            logger.error(f"LLM Gateway Error: {response['error']}")
            raise ValueError(f"LLM Gateway Error: {response['error']}")

        # Response is already validated in _make_request_with_retry
        content = self._clean_response_text(
            response["choices"][0]["message"]["content"]
        )
        chat_message = Message(role="assistant", content=content)
        logger.info(f"Successfully completed chat, response length: {len(content)}")
        return chat_message


class OpenRouterLLM:
    """Unified LLM client for OpenRouter API"""

    model_name_map = {
        "DeepSeek R1 New": "deepseek/deepseek-r1-0528",
        "DeepSeek R1": "deepseek/deepseek-r1",
        "Sonnet 3.7": "anthropic/claude-3.7-sonnet",
        "GPT 4o": "openai/gpt-4o-2024-08-06",
        "Gemini 2.5 Flash": "google/gemini-2.5-flash",
        "Gemini 2.5 Pro": "google/gemini-2.5-pro",
        "Qwen 3": "qwen/qwen3-235b-a22b",
    }

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro-preview-03-25",
        temperature: float = 0.7,
        max_tokens: int = 10000,
        **kwargs,
    ):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "your_openrouter_api_key")
        assert self.api_key != "your_openrouter_api_key", (
            "OpenRouter API key must be set"
        )

        # Map the model name to OpenRouter format
        self.model_name = self.model_name_map.get(model_name, model_name)
        self.base_url = os.environ.get(
            "OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Set up headers for API requests
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Create async client
        self.async_client = httpx.AsyncClient(
            headers=self.headers,
            timeout=httpx.Timeout(
                600.0, read=600.0, write=60.0
            ),  # Fixed timeout values
        )

        logger.info(f"Initialized OpenRouterLLM with model: {model_name}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.aclose()

    async def aclose(self):
        """Close the async client"""
        await self.async_client.aclose()
        logger.info("Closed OpenRouterLLM async client")

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata"""
        return LLMMetadata(
            context_window=100000,  # Adjust based on your model's context window
            num_output=self.max_tokens,
            model_name=self.model_name,
            is_chat_model=True,
        )

    @property
    def model(self) -> str:
        """Return model name for compatibility"""
        return self.model_name

    async def run_async(
        self,
        model_name: str,
        messages: List[Message],
        params: Optional[ModelParams] = None,
        images: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Make an async API request to the LLM Gateway"""
        if params is None:
            params = ModelParams()

        messages_dict = [asdict(msg) for msg in messages]
        payload = {
            "model": model_name,
            "messages": messages_dict,
            **asdict(params),
        }

        logger.debug(
            f"Making request to {self.base_url}/chat/completions with model: {model_name}"
        )

        try:
            response = await self.async_client.post(
                f"{self.base_url}/chat/completions", json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Handle HTTP status errors (4xx, 5xx)
            error_response = {
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "status_code": e.response.status_code,
                "stack_trace": traceback.format_exc(),
            }
            logger.error(f"HTTP Error {e.response.status_code}: {e.response.text}")
            return error_response
        except httpx.RequestError as e:
            # Handle network/connection errors
            error_response = {
                "error": f"Request failed: {str(e)}",
                "status_code": None,
                "stack_trace": traceback.format_exc(),
            }
            logger.error(f"Request failed: {str(e)}")
            return error_response
        except Exception as e:
            # Handle any other unexpected errors
            error_response = {
                "error": f"Unexpected error: {str(e)}",
                "status_code": None,
                "stack_trace": traceback.format_exc(),
            }
            logger.error(f"Unexpected error: {str(e)}")
            return error_response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_result(_should_retry_on_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
    )
    async def _make_request_with_retry(
        self, messages: List[Message], params: ModelParams
    ) -> Dict[str, Any]:
        """Make API request with retry logic using tenacity library"""
        logger.debug(f"Making request attempt to {self.base_url}")

        response = await self.run_async(
            model_name=self.model_name,
            messages=messages,
            params=params,
        )

        logger.debug(f"Response received: {response}")

        # If there's an explicit error in the response, return it for retry logic
        if "error" in response:
            logger.warning(f"Request failed with error: {response.get('error')}")
            return response

        # Validate response structure - if invalid, treat as error for retry
        try:
            choices = response.get("choices", [])
            if not choices or not isinstance(choices, list):
                logger.warning(
                    "Invalid response: no choices found or choices is not a list"
                )
                return {
                    "error": "Invalid response: no choices found or choices is not a list"
                }

            if len(choices) == 0:
                logger.warning("Invalid response: empty choices list")
                return {"error": "Invalid response: empty choices list"}

            message = choices[0].get("message", {})
            if not message or not isinstance(message, dict):
                logger.warning(
                    "Invalid response: no message found or message is not a dict"
                )
                return {
                    "error": "Invalid response: no message found or message is not a dict"
                }

            content = message.get("content", "")
            if not content or not isinstance(content, str):
                logger.warning(
                    "Invalid response: no content in message or content is not a string"
                )
                return {
                    "error": "Invalid response: no content in message or content is not a string"
                }

            # Response is valid
            logger.info("Request successful")
            return response

        except (KeyError, IndexError, AttributeError, TypeError) as e:
            logger.warning(f"Invalid response format: {e}")
            return {"error": f"Invalid response format: {e}"}

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Complete a prompt asynchronously"""
        messages = [Message(role="user", content=prompt)]
        params = ModelParams(
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        logger.info(
            f"Starting completion with temperature: {params.temperature}, max_tokens: {params.max_tokens}"
        )
        response = await self._make_request_with_retry(messages, params)

        if "error" in response:
            logger.error(f"LLM Gateway Error: {response['error']}")
            raise ValueError(f"LLM Gateway Error: {response['error']}")

        # Response is already validated in _make_request_with_retry
        content = self._clean_response_text(
            response["choices"][0]["message"]["content"]
        )
        logger.info(f"Successfully completed prompt, response length: {len(content)}")
        return CompletionResponse(text=content)

    def _clean_response_text(self, text: str) -> str:
        """Remove <think> tags and extract only the actual response content"""
        if not text:
            return ""

        # Remove <think>...</think> blocks (including multiline)
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        # Clean up extra whitespace and newlines
        cleaned = cleaned.strip()

        # Remove leading/trailing newlines
        while cleaned.startswith("\n"):
            cleaned = cleaned[1:]
        while cleaned.endswith("\n"):
            cleaned = cleaned[:-1]

        return cleaned

    async def ajson_complete(
        self,
        base_prompt: str,
        model: Type[T],
        max_retry: int = 3,
        **kwargs: Any,
    ) -> T:
        """Complete a prompt and return parsed JSON response"""
        json_prompt = f"""
{base_prompt}

IMPORTANT: Respond with ONLY valid JSON. Do not include any explanations, markdown formatting, or additional text. Your response must be a single, raw JSON object.

The JSON should match this schema:
{json.dumps(model.model_json_schema(mode="serialization"), indent=2)}
"""

        kwargs.setdefault("temperature", 0.1)
        logger.info(f"Starting JSON completion with {max_retry} max retries")
        response_text = ""

        for current_try in range(max_retry):
            try:
                # Call the async version
                response = await self.acomplete(json_prompt, **kwargs)
                response_text = response.text.strip()

                # Try to extract JSON from response
                json_match = re.search(r"{{.*}}", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(0)

                # Parse and validate JSON
                data = json.loads(response_text)
                parsed_model = model.model_validate(data)
                logger.info(
                    f"Successfully parsed JSON response on attempt {current_try + 1}"
                )
                return parsed_model

            except json.JSONDecodeError as e:
                if current_try < max_retry - 1:
                    json_prompt += f"\n\nThe response you provided: {response_text} is not in a valid JSON format. Please ensure your response is a valid JSON object that matches the schema provided above."
                    logger.warning(
                        f"JSON parsing failed (attempt {current_try + 1}/{max_retry}): {e}"
                    )
                    continue
                else:
                    logger.error(
                        f"Failed to parse JSON after {max_retry} retries. Last response: {response_text}"
                    )
                    raise ValueError(
                        f"Failed to parse JSON after {max_retry} retries. Last response: {response_text}"
                    )
            except Exception as e:
                if current_try < max_retry - 1:
                    logger.warning(
                        f"Error (attempt {current_try + 1}/{max_retry}): {e}"
                    )
                    continue
                else:
                    logger.error(
                        f"Failed to get valid response after {max_retry} retries: {e}"
                    )
                    raise ValueError(
                        f"Failed to get valid response after {max_retry} retries: {e}"
                    )

        # This should never be reached, but just in case
        logger.error(f"Failed to get valid JSON after {max_retry} retries")
        raise ValueError(f"Failed to get valid JSON after {max_retry} retries")

    async def chat_complete(
        self,
        messages: List[Message],
        **kwargs: Any,
    ) -> Message:
        """Complete a a chat conversation"""
        params = ModelParams(
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        logger.info(f"Starting chat completion with {len(messages)} messages")
        response = await self._make_request_with_retry(messages, params)

        if "error" in response:
            logger.error(f"LLM Gateway Error: {response['error']}")
            raise ValueError(f"LLM Gateway Error: {response['error']}")

        # Response is already validated in _make_request_with_retry
        content = self._clean_response_text(
            response["choices"][0]["message"]["content"]
        )
        chat_message = Message(role="assistant", content=content)
        logger.info(f"Successfully completed chat, response length: {len(content)}")
        return chat_message


class UnifiedLLM:
    """Unified LLM client that routes to appropriate backend based on model name"""

    # Define which models go to which provider
    KONG_MODELS = {
        "DeepSeek R1 New",
        "DeepSeek R1",
        "GPT 4o",
        "Nova Premier",
        "Gemini 2.5 Flash",
        "Gemini 2.5 Pro",
    }

    OPENROUTER_MODELS = {"Sonnet 3.7", "Qwen 3"}

    def __init__(
        self,
        model_name: str = "Gemini 2.5 Pro",
        temperature: float = 0.7,
        max_tokens: int = 10000,
        **kwargs,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

        # Route to appropriate provider
        if model_name in self.KONG_MODELS:
            self.provider = KongLLM(
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            self.provider_type = "kong"
        elif model_name in self.OPENROUTER_MODELS:
            self.provider = OpenRouterLLM(
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            self.provider_type = "openrouter"
        else:
            # Default to Kong for unknown models
            logger.warning(f"Unknown model {model_name}, defaulting to Kong provider")
            self.provider = KongLLM(
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            self.provider_type = "kong"

        logger.info(
            f"Initialized UnifiedLLM with model: {model_name}, provider: {self.provider_type}"
        )

    async def __aenter__(self):
        """Async context manager entry"""
        await self.provider.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.provider.__aexit__(exc_type, exc_val, exc_tb)

    async def aclose(self):
        """Close the underlying provider"""
        await self.provider.aclose()

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata from underlying provider"""
        return self.provider.metadata

    @property
    def model(self) -> str:
        """Return model name for compatibility"""
        return self.provider.model

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Complete a prompt asynchronously"""
        return await self.provider.acomplete(prompt, **kwargs)

    async def ajson_complete(
        self,
        base_prompt: str,
        model: Type[T],
        max_retry: int = 3,
        **kwargs: Any,
    ) -> T:
        """Complete a prompt and return parsed JSON response"""
        return await self.provider.ajson_complete(
            base_prompt, model, max_retry, **kwargs
        )

    async def chat_complete(
        self,
        messages: List[Message],
        **kwargs: Any,
    ) -> Message:
        """Complete a chat conversation"""
        return await self.provider.chat_complete(messages, **kwargs)


# For backward compatibility, create aliases
LLM = UnifiedLLM  # Main alias for external use


# # Example usage
# if __name__ == "__main__":
#     import os

#     async def test_llm():
#         # Test Kong model
#         logger.info("Testing UnifiedLLM routing...")
#         llm_kong = UnifiedLLM(model_name="Nova Premier")

#         # Test with a model that would go to OpenRouter (but skip if no API key)
#         try:
#             llm_openrouter = UnifiedLLM(model_name="Qwen 3")
#             has_openrouter = True
#         except AssertionError as e:
#             logger.warning(f"Skipping OpenRouter test: {e}")
#             llm_openrouter = None
#             has_openrouter = False

#         try:
#             # Test Kong provider
#             logger.info(f"Testing Kong provider with {llm_kong.provider_type}...")
#             response = await llm_kong.acomplete("Hello, how are you?")
#             logger.info(f"Kong completion: {response.text[:100]}...")

#             # Test OpenRouter provider if available
#             if has_openrouter and llm_openrouter:
#                 logger.info(
#                     f"Testing OpenRouter provider with {llm_openrouter.provider_type}..."
#                 )
#                 response = await llm_openrouter.acomplete(
#                     "What is the capital of France?"
#                 )
#                 logger.info(f"OpenRouter completion: {response.text[:100]}...")

#             # Test chat completion
#             messages = [Message(role="user", content="What is 2+2?")]
#             chat_response = await llm_kong.chat_complete(messages)
#             logger.info(f"Chat completion: {chat_response.content[:100]}...")

#         except Exception as e:
#             logger.error(f"Error: {e}")
#         finally:
#             await llm_kong.aclose()
#             if has_openrouter and llm_openrouter:
#                 await llm_openrouter.aclose()

#     # Run the test
#     asyncio.run(test_llm())

# Example usage
# if __name__ == "__main__":
#     chat_history = []



#     user = [Message(role="user",content=input("USER: "))]
    
#     while user.lower() not in ["quit", "exit"]:
#         async def main():
#             for model in KongLLM.model_name_map.keys():
#                 async with KongLLM(model_name=model) as llm:
#                     response = await llm.chat_complete(user)
#                     chat_history.append(response)
#                     print(f"{KongLLM.model_name_map[model]}: {response.text}")
#         asyncio.run(main())
#         user = input("USER: ")




