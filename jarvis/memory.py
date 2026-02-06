"""Memory management with semantic embeddings and chunked parquet storage."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
SIMILARITY_THRESHOLD = 0.3
MIN_RESULTS = 3

# Chunking params
CHUNK_SIZE = 250  # target chars per chunk
CHUNK_OVERLAP = 50  # overlap between chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, respecting sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    # split into sentences (roughly)
    sentences = re.split(r'(?<=[.!?\n])\s+', text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # if adding this sentence exceeds chunk_size and we have content, start new chunk
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # start new chunk with overlap from end of previous
            if overlap > 0 and len(current_chunk) > overlap:
                # find a good break point for overlap
                overlap_text = current_chunk[-overlap:]
                # try to start at word boundary
                space_idx = overlap_text.find(' ')
                if space_idx > 0:
                    overlap_text = overlap_text[space_idx+1:]
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence

    # add final chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


class MemoryManager:
    """Manage semantic memories with chunk-based embeddings."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.memories_path = self.data_dir / "memories.parquet"
        self.chunks_path = self.data_dir / "chunks.parquet"
        self.client = OpenAI()
        self._memories: Optional[pd.DataFrame] = None
        self._chunks: Optional[pd.DataFrame] = None
        self._chunk_embeddings: Optional[np.ndarray] = None

    def _load(self):
        """Load memories and chunks from parquet."""
        if self._memories is not None:
            return

        # load memories
        if self.memories_path.exists():
            self._memories = pd.read_parquet(self.memories_path)
        else:
            self._memories = pd.DataFrame(columns=["id", "content", "created_at"])

        # load chunks
        if self.chunks_path.exists():
            self._chunks = pd.read_parquet(self.chunks_path)
            if len(self._chunks) > 0:
                self._chunk_embeddings = np.vstack(self._chunks["embedding"].values)
            else:
                self._chunk_embeddings = np.zeros((0, EMBEDDING_DIM))
        else:
            self._chunks = pd.DataFrame(columns=["memory_id", "chunk_index", "chunk_text", "embedding"])
            self._chunk_embeddings = np.zeros((0, EMBEDDING_DIM))

    def _save(self):
        """Save memories and chunks to parquet."""
        self._memories.to_parquet(self.memories_path, index=False)
        self._chunks.to_parquet(self.chunks_path, index=False)

    def _embed(self, text: str) -> np.ndarray:
        """Get embedding for text using OpenAI."""
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def _embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Get embeddings for multiple texts in one API call."""
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        return [np.array(e.embedding, dtype=np.float32) for e in response.data]

    def save(self, content: str) -> str:
        """Save a memory with chunked embeddings."""
        self._load()

        memory_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # save memory
        new_memory = pd.DataFrame([{
            "id": memory_id,
            "content": content,
            "created_at": datetime.now().isoformat(),
        }])
        self._memories = pd.concat([self._memories, new_memory], ignore_index=True)

        # chunk and embed
        chunks = chunk_text(content)
        embeddings = self._embed_batch(chunks)

        # save chunks
        new_chunks = pd.DataFrame([
            {
                "memory_id": memory_id,
                "chunk_index": i,
                "chunk_text": chunk,
                "embedding": emb,
            }
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ])
        self._chunks = pd.concat([self._chunks, new_chunks], ignore_index=True)

        # update embedding matrix
        new_emb_matrix = np.vstack(embeddings)
        if len(self._chunk_embeddings) > 0:
            self._chunk_embeddings = np.vstack([self._chunk_embeddings, new_emb_matrix])
        else:
            self._chunk_embeddings = new_emb_matrix

        self._save()
        return memory_id

    def search(self, query: str, threshold: float = SIMILARITY_THRESHOLD, min_results: int = MIN_RESULTS) -> list[dict]:
        """Search memories by chunk similarity. Returns full memories, scored by best chunk match."""
        self._load()

        if len(self._chunks) == 0:
            return []

        query_embedding = self._embed(query)
        similarities = self._chunk_embeddings @ query_embedding

        # group by memory_id, take best chunk score per memory
        chunk_df = self._chunks.copy()
        chunk_df["similarity"] = similarities

        # get best similarity per memory
        best_per_memory = chunk_df.groupby("memory_id")["similarity"].max().reset_index()
        best_per_memory = best_per_memory.sort_values("similarity", ascending=False)

        results = []
        for _, row in best_per_memory.iterrows():
            sim = float(row["similarity"])
            memory_id = row["memory_id"]

            if sim >= threshold or len(results) < min_results:
                memory = self._memories[self._memories["id"] == memory_id].iloc[0]
                results.append({
                    "id": memory_id,
                    "content": memory["content"],
                    "similarity": sim,
                    "created_at": memory["created_at"],
                })
            else:
                break

        return results

    def get_all(self) -> list[dict]:
        """Get all memories."""
        self._load()
        return self._memories.to_dict("records") if len(self._memories) > 0 else []

    def delete(self, memory_id: str) -> bool:
        """Delete a memory and its chunks."""
        self._load()

        # check exists
        if memory_id not in self._memories["id"].values:
            return False

        # remove memory
        self._memories = self._memories[self._memories["id"] != memory_id].reset_index(drop=True)

        # remove chunks and rebuild embedding matrix
        self._chunks = self._chunks[self._chunks["memory_id"] != memory_id].reset_index(drop=True)
        if len(self._chunks) > 0:
            self._chunk_embeddings = np.vstack(self._chunks["embedding"].values)
        else:
            self._chunk_embeddings = np.zeros((0, EMBEDDING_DIM))

        self._save()
        return True
