import argparse
from dataclasses import asdict
import json

from .config import Settings
from .storage import seed_database
from .retrieval.graph import GraphRetriever


def main():
    parser = argparse.ArgumentParser(description="Assistant setup, retrieval, and agent chat")
    parser.add_argument("--root", default=".", help="Project root containing .env and data")
    parser.add_argument("--debug", action="store_true", help="Log step timings and sanitized failure details")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed")
    commands.add_parser("ingest")
    chat = commands.add_parser("chat", help="Start a passive terminal conversation with the agent")
    chat.add_argument("--debug", action="store_true", default=argparse.SUPPRESS,
                      help="Log step timings and sanitized failure details")
    agent = commands.add_parser("agent", help="Run one model-driven turn with discovered MCP tools")
    agent.add_argument("message")
    agent.add_argument("--trace", action="store_true")
    ask = commands.add_parser("ask", help="Run the centralized read-only informational pipeline")
    ask.add_argument("question")
    ask.add_argument("--context", default="")
    ask.add_argument("--trace", action="store_true", help="Print answer, sources, and trace as JSON")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=4)
    search.add_argument("--min-score", type=float, default=0.0)
    graph = commands.add_parser("graph")
    graph.add_argument("entity_id")
    graph.add_argument("--step", action="append", default=[], help="TYPE:out or TYPE:in; repeat for multi-hop")
    args = parser.parse_args()
    from .debug import configure
    configure(args.debug)
    if args.command == "chat":
        from .chat import connection_error, start_chat
        try:
            settings = Settings.load(args.root)
        except Exception as exc:
            print(connection_error(exc))
            raise SystemExit(1)
        raise SystemExit(start_chat(settings))
    settings = Settings.load(args.root)
    if args.command == "seed":
        seed_database(settings.sqlite_path, settings.root / "data/seed.json")
        print("Seed complete; existing records preserved.")
    elif args.command == "agent":
        import asyncio
        from .agent import connect_agent

        async def run_turn():
            async with connect_agent(settings) as session:
                result = await session.ask(args.message)
                result["discovered_tools"] = list(session.tool_names)
                print(json.dumps(result, indent=2, ensure_ascii=False) if args.trace else result["answer"])

        asyncio.run(run_turn())
    elif args.command == "ask":
        from .information import create_information_pipeline
        result = create_information_pipeline(settings).invoke(args.question, args.context)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.trace else result["answer"])
    elif args.command == "graph":
        steps = []
        for value in args.step:
            parts = value.split(":")
            if len(parts) != 2:
                parser.error("Each step must be TYPE:out or TYPE:in")
            steps.append(tuple(parts))
        result = GraphRetriever(settings.sqlite_path).traverse(args.entity_id, steps)
        print(json.dumps(asdict(result), indent=2))
    else:
        from .providers import embedding_provider
        from .retrieval.documents import ingest, DocumentRetriever
        embeddings = embedding_provider(settings)
        if args.command == "ingest":
            count = ingest(settings.sqlite_path, settings.root, settings.vector_index_path,
                           embeddings, settings.embedding_provider, settings.embedding_model)
            print(f"Index ready: {count} passages.")
        else:
            results = DocumentRetriever(settings.vector_index_path, embeddings,
                                        settings.embedding_provider, settings.embedding_model).search(
                                            args.query, top_k=args.top_k, min_score=args.min_score)
            print(json.dumps([asdict(result) for result in results], indent=2))


if __name__ == "__main__":
    main()
