from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = 'openai_api_key = os.getenv(\\"OPENAI_API_KEY\\")'
NEW = 'from src.llm import provider_name\\nprint(\\"provider\\", provider_name())'

def main() -> None:
    n = 0
    for p in ROOT.rglob("*.ipynb"):
        t = p.read_text(encoding="utf-8")
        if OLD not in t:
            continue
        p.write_text(t.replace(OLD, NEW), encoding="utf-8")
        print("keycell", p.relative_to(ROOT).as_posix())
        n += 1
    print("keycell_count", n)

if __name__ == "__main__":
    main()
