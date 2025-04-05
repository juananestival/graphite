import os
import shutil
import uuid
from pathlib import Path

import chromadb
from chromadb import Collection
from llama_index.embeddings.openai import OpenAIEmbedding
from simple_embedding_retrieval_assistant import SimpleEmbeddingRetrievalAssistant

from grafi.common.containers.container import container
from grafi.common.models.execution_context import ExecutionContext
from grafi.common.models.message import Message

api_key = os.getenv("OPENAI_API_KEY")

CURRENT_DIR = Path(__file__).parent
PERSIST_DIR = CURRENT_DIR / "storage"

event_store = container.event_store

# Delete the PERSIST_DIR and all files in it
if os.path.exists(PERSIST_DIR):
    shutil.rmtree(PERSIST_DIR)
    print(f"Deleted {PERSIST_DIR} and all its contents")


def get_execution_context() -> ExecutionContext:
    return ExecutionContext(
        conversation_id="conversation_id",
        execution_id=uuid.uuid4().hex,
        assistant_request_id=uuid.uuid4().hex,
    )


def get_embedding_model() -> OpenAIEmbedding:
    return OpenAIEmbedding(api_key=api_key)


def create_collection(document_path: Path = CURRENT_DIR / "data") -> Collection:
    # Create a persistent client
    client = chromadb.PersistentClient(path=str(PERSIST_DIR))

    # Try to get or create the collection
    try:
        collection = client.get_collection("aws-ec2")
        print("Using existing collection: aws-ec2")
    except:
        collection = client.create_collection("aws-ec2")
        print("Created new collection: aws-ec2")

        # Get embedding model
        embed_model = get_embedding_model()

        # Read files from document_path
        if document_path.exists() and document_path.is_dir():
            documents = []
            metadatas = []
            ids = []

            for i, file_path in enumerate(document_path.glob("*.*")):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:  # Skip empty documents
                            documents.append(content)
                            metadatas.append({"source": str(file_path.name)})
                            ids.append(f"doc_{i}")
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")

            # Add documents to collection if there are any
            if documents:
                # Embed documents
                embeddings = [embed_model.get_text_embedding(doc) for doc in documents]

                # Add documents with embeddings to the collection
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=embeddings,
                )
                print(f"Added {len(documents)} documents to the collection")

    return collection


def test_simple_embedding_retrieval_tool():
    execution_context = get_execution_context()
    simple_rag_assistant = (
        SimpleEmbeddingRetrievalAssistant.Builder()
        .name("SimpleEmbeddingRetrievalAssistant")
        .api_key(api_key)
        .embedding_model(get_embedding_model())
        .collection(create_collection())
        .build()
    )

    result = simple_rag_assistant.execute(
        execution_context,
        input_data=[
            Message(
                role="user",
                content="What is a service provided by Amazon Web Services that offers on-demand, scalable computing capacity in the cloud.",
            )
        ],
    )

    print(result)
    assert "Amazon EC2" in result[0].content
    print(len(event_store.get_events()))
    assert len(event_store.get_events()) == 11


test_simple_embedding_retrieval_tool()
