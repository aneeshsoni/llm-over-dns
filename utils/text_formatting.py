from typing import List, Tuple, Optional


def chunk_text_for_txt_record(text: str, max_chunk_bytes: int = 200) -> List[str]:
    """Split text into chunks that fit within a single DNS TXT string (<=255 bytes).

    We conservatively cap each chunk to max_chunk_bytes to account for encoding.
    """
    if not text:
        return [""]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for word in text.split():
        # Include space if current isn't empty
        add_len = (1 if current else 0) + len(word)
        if current_len + add_len > max_chunk_bytes:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            if current:
                current_len += 1  # space
            current.append(word)
            current_len += len(word)
    if current:
        chunks.append(" ".join(current))
    if not chunks:
        chunks = [""]
    return chunks


def extract_api_key_and_question(qname: object) -> Tuple[Optional[str], str]:
    """Extract API key and turn DNS labels into a human question.

    Strategy:
    - Look for "key-{apikey}" label at the beginning of the query
    - Join remaining labels with spaces: "what.is.life" -> "what is life"
    - Ignore the root label.
    - If a label starts with "b64-", try base64url decoding (optional feature).

    Returns:
        Tuple of (api_key, question) where api_key is None if not provided
    """
    from dnslib.label import DNSLabel
    import base64

    if isinstance(qname, str):
        qname = DNSLabel(qname)

    labels: List[bytes] = list(qname.label)
    if labels and labels[-1] == b"":  # trailing root
        labels = labels[:-1]

    api_key = None
    decoded_parts: List[str] = []

    for i, raw in enumerate(labels):
        try:
            s = raw.decode("utf-8", errors="replace")
        except Exception:
            s = str(raw)

        # Check if this is an API key label (should be first)
        if i == 0 and s.startswith("key-"):
            api_key = s[4:]  # Extract API key after "key-"
            continue

        if s.startswith("b64-"):
            enc = s[4:]
            try:
                # base64url without padding
                pad = "=" * (-len(enc) % 4)
                decoded = base64.urlsafe_b64decode((enc + pad).encode("ascii")).decode(
                    "utf-8", errors="replace"
                )
                decoded_parts.append(decoded)
                continue
            except Exception:
                pass
        # Handle spaces within labels (from quoted dig commands)
        # Replace underscores with spaces for better readability
        s = s.replace("_", " ")
        decoded_parts.append(s)

    # Join labels with spaces, but if there's only one label with spaces, use it as-is
    if len(decoded_parts) == 1 and " " in decoded_parts[0]:
        question = decoded_parts[0]
    else:
        question = " ".join(decoded_parts)

    return api_key, question


def labels_to_question(qname: object) -> str:
    """Turn DNS labels into a human question (backward compatibility).

    This function maintains backward compatibility by ignoring API keys.
    """
    _, question = extract_api_key_and_question(qname)
    return question
