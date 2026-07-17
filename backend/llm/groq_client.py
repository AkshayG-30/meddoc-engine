"""Groq LLM client wrapper.

Wraps the Groq SDK for generating QA test cases.
Uses LLaMA 3.3 70B Versatile for high-quality output.
"""

from groq import Groq
from backend.config import get_settings


_client = None


def get_groq_client() -> Groq:
    """Get Groq client instance (lazy singleton)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """Call the Groq LLM and return the response text.
    
    Args:
        system_prompt: System instruction for the LLM
        user_prompt: The actual prompt with document content
        model: Groq model to use
        temperature: Sampling temperature (lower = more deterministic)
        max_tokens: Maximum response length
    
    Returns:
        The LLM's response text
    
    Raises:
        Exception: If the API call fails
    """
    client = get_groq_client()
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    return response.choices[0].message.content
