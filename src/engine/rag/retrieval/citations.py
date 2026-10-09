from __future__ import annotations

import re
from pathlib import Path


class CitationManager:
    def filter_unused_citations( # this method is optional , its for 
        self,
        answer: str,
        source_map: dict | None = None,
        source_text: str | None = None,
        consolidate: bool = True,
    ) -> str | None:
        """
        Cross-references citations present in the answer (`[Source N]`) against the provided
        source map or source text. Removes sources that the LLM did not actually cite.
        Returns None if no sources were cited.
        """
        if not answer:
            return None

        # Extract cited IDs (e.g., [Source 1], [Source 1, 2], [Sources 2])
        matches = re.findall(r"\[Sources?\s*([0-9,\s]+)\]", answer, flags=re.IGNORECASE)
        cited_ids = set()
        for match in matches:
            for part in match.split(","):
                part_clean = part.strip()
                if part_clean.isdigit():
                    cited_ids.add(int(part_clean))

        # If no citations were used in the answer, return None
        if not cited_ids:
            return None

        # Filter structured source_map if provided
        if source_map:
            filtered_map = {
                sid: src
                for sid, src in source_map.items()
                if sid in cited_ids
            }
            if not filtered_map:
                return None
            return self.build_source_text(filtered_map, consolidate=consolidate)

        # Fallback: filter raw source_text blocks if source_map is omitted
        if source_text:
            blocks = source_text.strip().split("\n\n")
            kept_blocks = []
            for block in blocks:
                block_matches = re.findall(r"\[Sources?\s*([0-9,\s]+)\]", block, flags=re.IGNORECASE)
                block_ids = set()
                for bm in block_matches:
                    for p in bm.split(","):
                        if p.strip().isdigit():
                            block_ids.add(int(p.strip()))
                if block_ids & cited_ids:
                    kept_blocks.append(block)
            return "\n\n".join(kept_blocks) if kept_blocks else None

        return None

    @staticmethod
    def format_page_range(pages: list[int] | set[int] | None) -> str:
        """
        Converts a list of page numbers into a clean, human-readable range string.
        Examples:
            [1, 2, 3] -> "1-3"
            [2, 4, 5, 6, 9] -> "2, 4-6, 9"
            [5] -> "5"
            [] -> "N/A"
        """
        if not pages:
            return "N/A"

        # Deduplicate and sort valid integers
        sorted_pages = sorted({
            int(p)
            for p in pages
            if isinstance(p, (int, str)) and str(p).isdigit()
        })
        if not sorted_pages:
            return "N/A"

        ranges = []
        start = sorted_pages[0]
        end = sorted_pages[0]

        for p in sorted_pages[1:]:
            if p == end + 1:
                end = p
            else:
                ranges.append(str(start) if start == end else f"{start}-{end}")
                start = p
                end = p

        ranges.append(str(start) if start == end else f"{start}-{end}")
        return ", ".join(ranges)

    def build_source_text(self, source_map: dict, consolidate: bool = True) -> str:
        """
        Builds clean, formatted source text from source_map.
        When consolidate=True, combines chunks originating from the same file.
        """
        if not source_map:
            return ""

        if not consolidate:
            sources = []
            for source_id, source in source_map.items():
                raw_file = source.get("file", "")
                file_name = Path(raw_file).name if raw_file else "Document"
                page_str = self.format_page_range(source.get("pages", []))
                sources.append(
                    f"[Source {source_id}]\nFile: {file_name}\nPages: {page_str}"
                )
            return "\n\n".join(sources)

        # Group by unique document filename
        grouped: dict[str, dict] = {}
        for source_id, source in source_map.items():
            raw_file = source.get("file", "")
            file_name = Path(raw_file).name if raw_file else "Document"
            pages = source.get("pages", [])

            if file_name not in grouped:
                grouped[file_name] = {
                    "source_ids": [source_id],
                    "pages": list(pages),
                }
            else:
                grouped[file_name]["source_ids"].append(source_id)
                grouped[file_name]["pages"].extend(pages)

        sources = []
        for file_name, data in grouped.items():
            s_ids = data["source_ids"]
            s_label = (
                f"[Source {s_ids[0]}]"
                if len(s_ids) == 1
                else f"[Source {', '.join(map(str, s_ids))}]"
            )
            page_str = self.format_page_range(data["pages"])
            sources.append(
                f"{s_label}\nFile: {file_name}\nPages: {page_str}"
            )

        return "\n\n".join(sources)

    def resolve_citation(self, source_id, source_map):
        return source_map.get(source_id)
