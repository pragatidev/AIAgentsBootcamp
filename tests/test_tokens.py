"""S3.3 stuffed prompt is larger. Local encoding."""

import tiktoken


def test_stuffed_prompt_has_more_tokens():
    enc = tiktoken.get_encoding("cl100k_base")
    short = enc.encode("Can I return this order?")
    stuffed = enc.encode("Can I return this order? " + ("policy wiki page. " * 80))
    assert len(stuffed) > len(short)
    assert len(short) > 0
