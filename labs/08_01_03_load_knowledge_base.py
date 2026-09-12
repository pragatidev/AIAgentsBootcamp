# %% [markdown]
# Load the DataFlow knowledge base.
#
# When this works, twenty files go in, many more documents come out,
# one csv row still carries its billing number, and the library json
# loader prints the jq ImportError so you know why we wrote load_json
# by hand. Then skip the csv loader: the billing row is no longer a
# separate document. Put CSVLoader back and the row returns.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.document_loaders import CSVLoader, TextLoader

from dataflow.rag.load import (
    KB_DIR,
    list_knowledge_files,
    load_json,
    load_knowledge_base,
)

files = list_knowledge_files()
docs = load_knowledge_base()
print("file_count", len(files))
print("document_count", len(docs))

csv_docs = [
    doc
    for doc in docs
    if str(doc.metadata.get("source", "")).endswith("billing_and_pricing.csv")
]
print("billing_csv_documents", len(csv_docs))
billing = csv_docs[0]
print("billing_row_content")
print(billing.page_content[:200])
print("billing_row_metadata", billing.metadata)

# %%
json_path = (
    KB_DIR
    / "internal_operations"
    / "product_releases"
    / "release_notes.json"
)
try:
    from langchain_community.document_loaders import JSONLoader

    JSONLoader(file_path=str(json_path), jq_schema=".releases[]").load()
    print("JSONLoader_unexpected_success")
except Exception as err:
    print("JSONLoader_error", type(err).__name__ + ":", err)

hand = load_json(json_path)
print("load_json_documents", len(hand))
print("load_json_source", hand[0].metadata.get("source"))
print("load_json_record", hand[0].metadata.get("record"))

# %%
csv_path = KB_DIR / "business_data" / "billing_and_pricing.csv"
broken = TextLoader(str(csv_path), encoding="utf-8").load()
print("break_textloader_csv_documents", len(broken))
print("break_textloader_csv_length", len(broken[0].page_content))
print(
    "billing_feature_row_is_separate",
    len(broken) > 1 and "Number of users" in broken[0].page_content[:80],
)
print(
    "break_note",
    "one document, the billing feature row is no longer a separate document",
)

# %%
restored = CSVLoader(str(csv_path), encoding="utf-8").load()
print("restore_csv_documents", len(restored))
print("restore_row_in_metadata", "row" in restored[0].metadata)
print("restore_content_start")
print(restored[0].page_content[:200])
