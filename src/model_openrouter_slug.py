"""
The 6 models under test, as OpenRouter slugs.
Kept as a list of (display_name, slug) so output tables show friendly names.
"""
MODELS = [
    ("GPT-5.6 Terra",        "openai/gpt-5.6-terra"),
    ("Kimi K3",              "moonshotai/kimi-k3"),
    ("DeepSeek-V4-Pro-0813", "deepseek/deepseek-v4-pro"),
    ("Qwen3.8 Max",          "qwen/qwen3.8-max"),
    ("Grok 4.6",             "x-ai/grok-4.6"),
    ("Claude Sonnet 5",      "anthropic/claude-sonnet-5"),
]

if __name__ == "__main__":
    print(f"{len(MODELS)} models under test:")
    for name, slug in MODELS:
        print(f"  {name:22s} -> {slug}")
        