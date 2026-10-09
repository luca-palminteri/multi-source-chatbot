"""Prepare persistent container data before starting the HTTP services."""
from .config import Settings
from .providers import embedding_provider
from .retrieval.documents import ingest
from .storage import seed_database


def initialize(settings: Settings):
    # Seeding is idempotent and preserves existing action state. Running it again
    # also recovers a startup interrupted before all seed records were committed.
    print("Preparing database; existing records are preserved.", flush=True)
    seed_database(settings.sqlite_path, settings.root / "data/seed.json")
    print("Checking document index; embedding new or changed sources if needed.", flush=True)
    # Ingestion compares the source/provider/model fingerprint before making an
    # embedding call and replaces the index atomically only after success.
    count = ingest(settings.sqlite_path, settings.root, settings.vector_index_path,
                   embedding_provider(settings), settings.embedding_provider,
                   settings.embedding_model)
    print(f"Startup data ready: {count} passages.", flush=True)


if __name__ == "__main__":
    initialize(Settings.load())
