import os
from pathlib import Path

import chromadb
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "data" / "helpdesk.parquet"
CHROMA_DIR = ROOT / "chroma_db"
COLLECTION = "helpdesk"
EMBED_MODEL = "text-embedding-3-small"
BATCH = 100


def embed(client, texts):
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def main():
    df = pd.read_parquet(RECORDS)
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        chroma.delete_collection(COLLECTION)
    except Exception:
        pass
    col = chroma.create_collection(COLLECTION)

    for i in range(0, len(df), BATCH):
        batch = df.iloc[i:i + BATCH]
        vectors = embed(client, batch["text"].tolist())
        col.add(
            ids=[str(x) for x in batch["Id"]],
            embeddings=vectors,
            documents=batch["text"].tolist(),
            metadatas=[
                {
                    "system": r.system,
                    "question": r.question,
                    "reply": r.reply,
                    "assignee": r.assignee,
                    "completed_at": r.completed_at,
                }
                for r in batch.itertuples()
            ],
        )
        print(f"embedded {min(i + BATCH, len(df))}/{len(df)}")

    print(f"done: {col.count()} records in {CHROMA_DIR}")


if __name__ == "__main__":
    main()
