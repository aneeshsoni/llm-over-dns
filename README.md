LLM-over-DNS
============

Answer DNS TXT queries using an LLM (OpenAI, Anthropic, or Gemini). This lets you query LLMs directly via DNS:

```
dig @127.0.0.1 -p 5353 what.is.the.meaning.of.life TXT +short
```

How It Works
------------

This system bridges DNS and LLMs through a clever encoding scheme:

1. **DNS Query**: You send a DNS TXT query where the domain name encodes your question
   ```
   dig @127.0.0.1 -p 5353 what.is.the.meaning.of.life TXT +short
   ```

2. **Domain Parsing**: The DNS server extracts the domain labels `["what", "is", "the", "meaning", "of", "life"]`

3. **Text Reconstruction**: Labels are joined with spaces to form the question: `"what is the meaning of life"`

4. **LLM Processing**: The question is sent to your chosen LLM provider (OpenAI, Anthropic, or Gemini)

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
  - Joins labels with spaces: `["what", "is", "life"]` → `"what is life"`
- `chunk_text_for_txt_record()`: Long text → DNS-compatible chunks
  - Splits responses to fit 255-byte TXT string limits
  - Preserves word boundaries when possible

**LLM Integration** (`utils/ai_providers.py`):
- `generate_with_provider()`: Routes to OpenAI, Anthropic, or Gemini APIs
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
- Dots as spaces: `what.is.life` → `"what is life"`
- Underscores as spaces: `what_is_life` → `"what is life"`  
- URL encoding: `what%20is%20life` → `"what is life"`
- Base64 for complex queries: `b64-encoded_prompt`

Notes
-----
- Default port is 5353 to avoid root privileges; DNS default is 53.
- Each TXT record string is limited to 255 bytes. The server splits the response into multiple strings; clients will show them contiguously.
- UDP DNS packets are typically limited to ~512 bytes without EDNS0. The server truncates long LLM output to fit (about 400 chars by default).

Setup
-----
1. Python 3.11+
2. Install dependencies
3. Set your API key(s)
4. Run the server:

```
python main.py --host 0.0.0.0 --port 5353 --provider openai
python main.py --host 0.0.0.0 --port 5353 --provider anthropic
python main.py --host 0.0.0.0 --port 5353 --provider gemini
```

Usage Options
-------------

**Option 1: Dots as word separators**
```
dig @127.0.0.1 -p 5353 what.is.the.meaning.of.life TXT +short
```

**Option 2: Underscores as spaces (more natural)**
```
dig @127.0.0.1 -p 5353 what_is_the_meaning_of_life TXT +short
```

**Option 3: URL-encoded spaces**
```
dig @127.0.0.1 -p 5353 what%20is%20the%20meaning%20of%20life TXT +short
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

Custom Models
-------------
Override default models:

```
python main.py --provider openai --model gpt-4o
python main.py --provider anthropic --model claude-3-5-sonnet-20241022
python main.py --provider gemini --model gemini-1.5-pro
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
- Rate limiting per source IP
- Request authentication or allowlist
- Model output length limits (already implemented)
- Observability/logging

License
-------
MIT
