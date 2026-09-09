# %%
"""S3.3 Token counts. Local encoding. No API key."""

import tiktoken

# %%
enc = tiktoken.get_encoding("cl100k_base")

short = "Can I return this order?"
stuffed = short + " " + ("policy wiki page. " * 80)

# %%
short_n = len(enc.encode(short))
stuffed_n = len(enc.encode(stuffed))
print("encoding", "cl100k_base")
print("short_tokens", short_n)
print("stuffed_tokens", stuffed_n)
print("stuffed_is_larger", stuffed_n > short_n)
