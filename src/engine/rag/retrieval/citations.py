class CitationManager:
    def build_source_text(self, source_map):
        sources = []

        for source_id, source in source_map.items():
            sources.append(
                f"[Source {source_id}]\n"
                f"File: {source['file']}\n"
                f"Pages: {source['pages']}"
            )

        return "\n\n".join(sources)

    def resolve_citation(self, source_id, source_map):
        return source_map.get(source_id)


if __name__ == "__main__":
    manager = CitationManager()

    sample_source_map = {
        1: {"chunk_id": 2, "file": "benchmark_data/aiml.pdf", "pages": [2, 3]},
        2: {"chunk_id": 1, "file": "benchmark_data/aiml.pdf", "pages": [1, 2, 3]},
    }

    print("===== SOURCES TEXT =====")
    print(manager.build_source_text(sample_source_map))

    print("===== RESOLVED CITATION =====")
    print("Source 1:", manager.resolve_citation(1, sample_source_map))