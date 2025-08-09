LLM-over-DNS
============

Answer DNS TXT queries using an LLM (OpenAI or Anthropic). This lets you query LLMs directly via DNS:

```
dig @127.0.0.1 -p 5353 summarize.interstellar.for.me TXT +short
```

## Table of Contents

- [How It Works](#how-it-works)
- [Server Architecture](#server-architecture)
- [Notes](#notes)
- [Setup](#setup)
  - [Quick Start with uv (Recommended)](#quick-start-with-uv-recommended)
  - [Traditional Python Setup](#traditional-python-setup)
- [Usage Options](#usage-options)
  - [Without API Key Protection](#without-api-key-protection)
  - [With API Key Protection](#with-api-key-protection)
- [Custom Models](#custom-models)
- [Response Length Control](#response-length-control)
- [Running on port 53](#running-on-port-53)
- [Security](#security)
  - [API Key Protection (Built-in)](#api-key-protection-built-in)
  - [Additional Security Measures](#additional-security-measures)
- [License](#license)

How It Works
------------

This system bridges DNS and LLMs through a clever encoding scheme:

1. **DNS Query**: You send a DNS TXT query where the domain name encodes your question
   ```
   dig @127.0.0.1 -p 5353 summarize.interstellar.for.me TXT +short
   ```

2. **Domain Parsing**: The DNS server extracts the domain labels `["summarize", "interstellar", "for", "me"]`

3. **Text Reconstruction**: Labels are joined with spaces to form the question: `"summarize interstellar for me"`

4. **LLM Processing**: The question is sent to your chosen LLM provider (OpenAI or Anthropic)

5. **Response Formatting**: The LLM response is chunked to fit DNS TXT record limits (≤255 bytes per string)

6. **DNS Response**: The server returns the answer as DNS TXT records that dig displays

Server Architecture
-------------------

The running server handles DNS-to-LLM translation through several components:

**DNS Server Layer** (`main.py`):
- Listens on UDP/TCP ports (default 5353) using `dnslib`
- Accepts only TXT record queries (returns NOTIMP for other types)
- Spawns threads for concurrent request handling

**Request Processing** (`LLMResolver.resolve()`):
1. Extracts `qname` (domain name) from incoming DNS request
2. Calls `labels_to_question()` to convert DNS labels to natural language
3. Calls `llm_answer()` to get LLM response
4. Calls `chunk_text_for_txt_record()` to split response for DNS TXT format
5. Constructs DNS reply with TXT records containing the chunked response

**Text Processing** (`utils/text_formatting.py`):
- `labels_to_question()`: DNS labels → human-readable question
  - Handles dots, underscores, URL encoding, base64 encoding
  - Joins labels with spaces: `["summarize", "interstellar", "for", "me"]` → `"summarize interstellar for me"`
- `chunk_text_for_txt_record()`: Long text → DNS-compatible chunks
  - Splits responses to fit 255-byte TXT string limits
  - Preserves word boundaries when possible

**LLM Integration** (`utils/ai_providers.py`):
- `generate_with_provider()`: Routes to OpenAI or Anthropic APIs
- Handles model selection, API key management, error handling
- Truncates responses to ~400 chars to fit UDP packet limits
- Returns plain text responses ready for DNS encoding

**Configuration** (`config.py`):
- Loads API keys from environment variables via `python-dotenv`
- Manages provider-specific settings and defaults

**Why DNS?** 
- Universal protocol - works anywhere with internet access
- No special clients needed - just use `dig` 
- Bypasses many firewalls and proxies
- Demonstrates creative protocol abuse 😉

**Encoding Options:**
- Dots as spaces: `summarize.interstellar.for.me` → `"summarize interstellar for me"`
- Underscores as spaces: `summarize_interstellar_for_me` → `"summarize interstellar for me"`  
- URL encoding: `summarize%20interstellar%20for%20me` → `"summarize interstellar for me"`
- Base64 for complex queries: `b64-encoded_prompt`

Notes
-----
- Default port is 5353 to avoid root privileges; DNS default is 53.
- Each TXT record string is limited to 255 bytes. The server splits the response into multiple strings; clients will show them contiguously.
- UDP DNS packets are typically limited to ~512 bytes without EDNS0. The server truncates long LLM output to fit (about 400 chars by default).

Setup
-----

### Quick Start with uv (Recommended)

1. **Install [uv](https://docs.astral.sh/uv/)** if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and run** (uv handles Python version and dependencies automatically):
   ```bash
   git clone <this-repo-url>
   cd llm-over-dns
   ```

3. **Set your API key(s)** in `.env` file:
   ```bash
   cp .env.template .env
   ```
   Set your API key values

4. **Run the server** (uv automatically manages the environment):
   ```bash
   # Basic server
   uv run main.py --host 0.0.0.0 --port 5353 --provider openai
   
   # With API key protection
   uv run main.py --host 0.0.0.0 --port 5353 --provider openai --require-api-key
   
   # Other providers
   uv run main.py --host 0.0.0.0 --port 5353 --provider anthropic
   ```

### Traditional Python Setup

1. **Python 3.11+**
2. **Install dependencies:**
   ```bash
   pip install -e .
   # or
   pip install dnslib openai anthropic python-dotenv
   ```
3. **Set API keys** (same as above)
4. **Run the server:**
   ```bash
   python main.py --host 0.0.0.0 --port 5353 --provider openai --require-api-key
   ```

Usage Options
-------------

### Without API Key Protection

**Option 1: Dots as word separators**
```
dig @127.0.0.1 -p 5353 summarize.interstellar.for.me TXT +short
```

**Option 2: Underscores as spaces (more natural)**
```
dig @127.0.0.1 -p 5353 summarize_interstellar_for_me TXT +short
```

**Option 3: URL-encoded spaces**
```
dig @127.0.0.1 -p 5353 summarize%20interstellar%20for%20me TXT +short
```

**Option 4: Base64url-encoded prompt (for complex queries)**
```
PROMPT='Give me three bullet points about DNS over HTTPS vs classic DNS.'
ENC=$(python - <<'PY'
import base64,os
s=os.environ['PROMPT'].encode()
print(base64.urlsafe_b64encode(s).decode().rstrip('='))
PY
)
dig @127.0.0.1 -p 5353 b64-$ENC TXT +short
```

### With API Key Protection

When `--require-api-key` is enabled, queries must include the API key as the first DNS label with `key-` prefix:

**Basic authenticated query:**
```
dig @127.0.0.1 -p 5353 key-your_secret_key.summarize.interstellar.for.me TXT +short
```

**With underscores:**
```
dig @127.0.0.1 -p 5353 key-your_secret_key.summarize_interstellar_for_me TXT +short
```

**With base64 encoding:**
```
dig @127.0.0.1 -p 5353 key-your_secret_key.b64-$ENC TXT +short
```

**Unauthorized queries will return REFUSED:**
```bash
# Without API key (will fail)
dig @127.0.0.1 -p 5353 summarize.interstellar.for.me TXT +short

# With wrong API key (will fail)
dig @127.0.0.1 -p 5353 key-wrong_key.summarize.interstellar.for.me TXT +short
```

Custom Models
-------------
Override default models:

```
python main.py --provider openai --model gpt-4o
python main.py --provider anthropic --model claude-3-7-sonnet-20250219
```

Response Length Control
-----------------------
By default, responses are limited to 800 characters for DNS compatibility. You can customize this:

**Limited responses (recommended for reliability):**
```bash
python main.py --host 127.0.0.1 --port 5353 --provider openai --max-chars 800
```

**Unlimited responses (use with TCP):**
```bash
# Start server with unlimited responses
python main.py --host 127.0.0.1 --port 5353 --provider openai --max-chars 0

# Query with TCP to avoid UDP packet size limits
dig @127.0.0.1 -p 5353 +tcp "explain quantum computing in detail" TXT +short
```

**Custom limits:**
```bash
python main.py --host 127.0.0.1 --port 5353 --provider openai --max-chars 1500
```

**Why use TCP for longer responses?**
- UDP DNS packets are limited to ~512 bytes traditionally
- TCP supports much larger responses
- Use `+tcp` flag in dig for reliable delivery of long responses

Running on port 53
------------------
Use sudo if you need the standard DNS port:

```
sudo python main.py --port 53 --provider anthropic
```

Security
--------
This is a demo. Exposing an LLM-backed DNS to the public Internet can be costly and abused. Consider:

### API Key Protection (Built-in)
Enable with `--require-api-key` flag and set `DNS_API_KEY` in your `.env` file:
- Only requests with the correct API key will receive responses
- Unauthorized requests get DNS REFUSED response
- API key is embedded in the DNS query itself: `key-your_secret_key.your.question`

### Additional Security Measures
- Rate limiting per source IP
- Firewall rules to restrict access
- Model output length limits (already implemented)
- Observability/logging
- Regular API key rotation

License
-------
Apache
