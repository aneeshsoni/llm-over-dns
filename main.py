import argparse
import signal
import threading
from typing import Optional

from dnslib import CLASS, QTYPE, RCODE, RR, TXT, DNSRecord
from dnslib.server import DNSServer, BaseResolver, DNSLogger

from utils.ai_providers import generate_with_provider
from utils.text_formatting import (
    chunk_text_for_txt_record,
    extract_api_key_and_question,
)
from config import DNS_API_KEY


class LLMResolver(BaseResolver):
    def __init__(
        self,
        provider_name: str,
        model: Optional[str] = None,
        max_output_chars: int = 800,
        require_api_key: bool = False,
    ):
        self.provider_name = provider_name
        self.model = model
        # Keep payload small enough for UDP (~512 bytes). 800 chars split into 4x200-byte TXT chunks.
        self.max_output_chars = max_output_chars
        self.require_api_key = require_api_key

    def llm_answer(self, question: str) -> str:
        answer = generate_with_provider(
            question, provider=self.provider_name, model=self.model
        )
        # Replace common UTF-8 characters with ASCII equivalents for better DNS display
        answer = (
            answer.replace(""", "'").replace(""", "'")
            .replace('"', '"')
            .replace('"', '"')
            .replace("—", "--")
            .replace("–", "-")
            .replace("…", "...")
        )

        if self.max_output_chars > 0 and len(answer) > self.max_output_chars:
            answer = answer[: self.max_output_chars - 10].rstrip() + "..."
        return answer

    def resolve(self, request: DNSRecord, handler):  # type: ignore[override]
        qname = request.q.qname
        qtype = request.q.qtype
        reply = request.reply()

        if qtype != QTYPE.TXT:
            reply.header.rcode = RCODE.NOTIMP
            return reply

        # Extract API key and question from the DNS query
        provided_api_key, question = extract_api_key_and_question(qname)

        # Check API key authentication if required
        if self.require_api_key:
            if not DNS_API_KEY:
                # Server misconfiguration: API key required but not set
                reply.header.rcode = RCODE.SERVFAIL
                return reply

            if provided_api_key != DNS_API_KEY:
                # Authentication failed - return REFUSED
                reply.header.rcode = RCODE.REFUSED
                return reply

        answer = self.llm_answer(question)

        txt_chunks = chunk_text_for_txt_record(answer, max_chunk_bytes=200)
        reply.add_answer(
            RR(
                rname=qname,
                rtype=QTYPE.TXT,
                rclass=CLASS.IN,
                ttl=0,
                rdata=TXT(txt_chunks),
            )
        )
        return reply


def run_server(
    host: str,
    port: int,
    provider_name: str,
    model: Optional[str] = None,
    max_output_chars: int = 800,
    require_api_key: bool = False,
) -> None:
    resolver = LLMResolver(provider_name, model, max_output_chars, require_api_key)

    logger = DNSLogger(prefix=False)
    udp_server = DNSServer(resolver, port=port, address=host, logger=logger)
    tcp_server = DNSServer(resolver, port=port, address=host, tcp=True, logger=logger)

    udp_server.start_thread()
    tcp_server.start_thread()

    print(
        f"LLM-over-DNS listening on {host}:{port} (UDP/TCP), provider={provider_name}"
    )
    stop_event = threading.Event()

    def handle_sigint(signum, frame):  # pragma: no cover
        stop_event.set()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        while not stop_event.is_set():
            stop_event.wait(0.5)
    finally:
        udp_server.stop()
        tcp_server.stop()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-over-DNS: answer TXT queries with an LLM response"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Listen address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5353,
        help="Listen port (default: 5353; use 53 with sudo)",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic"],
        default="openai",
        help="LLM provider to use (default: openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (default depends on provider)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=800,
        help="Max response characters (0 = unlimited, default: 800)",
    )
    parser.add_argument(
        "--systemprompt",
        dest="system_prompt",
        default=None,
        help="Optional system prompt prefix",
    )
    parser.add_argument(
        "--require-api-key",
        action="store_true",
        help="Require API key authentication for queries (set DNS_API_KEY in .env)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    run_server(
        args.host,
        args.port,
        provider_name=args.provider,
        model=args.model,
        max_output_chars=args.max_chars,
        require_api_key=args.require_api_key,
    )


if __name__ == "__main__":
    main()
