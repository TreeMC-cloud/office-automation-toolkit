    from __future__ import annotations


    def _clean_text(value: str) -> str:
        return " ".join(str(value).replace("
", " ").split())


    def deduplicate_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        cleaned: list[dict[str, str]] = []
        for record in records:
            title = _clean_text(record.get("title", ""))
            url = _clean_text(record.get("url", ""))
            identity = (title, url)
            if identity in seen:
                continue
            seen.add(identity)
            cleaned.append({key: _clean_text(value) for key, value in record.items()})
        return cleaned
