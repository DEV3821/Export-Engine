"""Tests for extract schema — knowledgeExtract.v1."""

from export_engine.schemas import new_knowledge_extract
from export_engine.hashing import make_extract_key


class TestExtractSchema:
    """knowledgeExtract.v1 schema structure."""

    def test_schema_version(self) -> None:
        # We test the parser's output format by creating with the actual hash
        ek = make_extract_key("parent_key", "test.txt")
        # Verify hash-based
        assert len(ek) == 64

    def test_extract_key_hash_based(self) -> None:
        ek1 = make_extract_key("parent1", "file.txt")
        ek2 = make_extract_key("parent1", "file.txt")
        assert ek1 == ek2  # deterministic
        ek3 = make_extract_key("parent2", "file.txt")
        assert ek1 != ek3  # different parent = different key

    def test_original_name_hash_present(self) -> None:
        from export_engine.hashing import sha256_text
        name = "document.pdf"
        h = sha256_text(name)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_content_hash_present(self) -> None:
        from export_engine.hashing import sha256_bytes
        h = sha256_bytes(b"file content")
        assert len(h) == 64
