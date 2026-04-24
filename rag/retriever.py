import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "chroma_db"
COLLECTION = "helpdesk"
EMBED_MODEL = "text-embedding-3-small"


class HelpdeskRetriever:

    def __init__(self):
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.col = self.chroma.get_collection(COLLECTION)

    async def search(self, query: str, k: int = 5):
        resp = await self.openai.embeddings.create(model=EMBED_MODEL, input=[query])
        vec = resp.data[0].embedding
        res = self.col.query(query_embeddings=[vec], n_results=k)
        hits = []
        for i in range(len(res["ids"][0])):
            hits.append({
                "id": res["ids"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i],
            })
        return hits
