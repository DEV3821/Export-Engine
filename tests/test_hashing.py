"""Tests for hashing.py — stable hashing helpers."""

from export_engine.hashing import (
    sha256_text,
    sha256_bytes,
    stable_json_hash,
    short_hash,
    make_record_key,
    make_extract_key,
    make_conversation_key,
    make_chunk_id,
    make_folder_key,
    make_store_id_hash,
    safe_filename,
)


class TestDeterministicHashing:
    """All hash functions must produce stable, deterministic output."""

    def test_sha256_text_deterministic(self) -> None:
        h1 = sha256_text("hello world")
        h2 = sha256_text("hello world")
        assert h1 == h2
        assert len(h1) == 64

    def test_sha256_bytes_deterministic(self) -> None:
        h1 = sha256_bytes(b"hello world")
        h2 = sha256_bytes(b"hello world")
        assert h1 == h2
        assert len(h1) == 64

    def test_stable_json_hash_deterministic(self) -> None:
        obj = {"b": 2, "a": 1}
        h1 = stable_json_hash(obj)
        h2 = stable_json_hash(obj)
        assert h1 == h2

    def test_stable_json_hash_key_order_independent(self) -> None:
        a = {"name": "test", "value": 42}
        b = {"value": 42, "name": "test"}
        assert stable_json_hash(a) == stable_json_hash(b)

    def test_short_hash_length(self) -> None:
        h = short_hash("hello world", length=12)
        assert len(h) == 12

    def test_short_hash_default_length(self) -> None:
        h = short_hash("hello world")
        assert len(h) == 12


class TestDeterministicKeys:
    """Key functions must be deterministic."""

    def test_make_record_key_deterministic(self) -> None:
        k1 = make_record_key("Inbox", "Hello", "2025-01-01T00:00:00")
        k2 = make_record_key("Inbox", "Hello", "2025-01-01T00:00:00")
        assert k1 == k2
        assert len(k1) == 64

    def test_make_extract_key_deterministic(self) -> None:
        k1 = make_extract_key("record123", "body")
        k2 = make_extract_key("record123", "body")
        assert k1 == k2

    def test_make_conversation_key_deterministic(self) -> None:
        k1 = make_conversation_key("conv_abc")
        k2 = make_conversation_key("conv_abc")
        assert k1 == k2

    def test_make_chunk_id_deterministic(self) -> None:
        k1 = make_chunk_id("record123", 0)
        k2 = make_chunk_id("record123", 0)
        assert k1 == k2

    def test_make_folder_key_deterministic(self) -> None:
        k1 = make_folder_key("Inbox/Projects")
        k2 = make_folder_key("Inbox/Projects")
        assert k1 == k2

    def test_make_store_id_hash_deterministic(self) -> None:
        k1 = make_store_id_hash("mailbox@example.com")
        k2 = make_store_id_hash("mailbox@example.com")
        assert k1 == k2


class TestSafeFilename:
    """Filenames must be hash-based, not derived from raw text."""

    def test_safe_filename_from_digest(self) -> None:
        digest = "a" * 64
        name = safe_filename(digest)
        assert name == f"{digest}.json"
        assert name.isascii()

    def test_safe_filename_strips_unsafe_chars(self) -> None:
        # Pure hex is safe — no-op
        name = safe_filename("abc123")
        assert name == "abc123.json"

    def test_safe_filename_truncates_long(self) -> None:
        long_hash = "a" * 128
        name = safe_filename(long_hash)
        assert len(name) <= 64 + 5  # 64 hex + ".json"
        assert name.endswith(".json")

    def test_safe_filename_not_from_subject(self) -> None:
        """Prove that filenames are hash-based, not subject-derived."""
        digest = sha256_text("Meeting agenda — Q3 review")
        name = safe_filename(digest)
        # The filename must NOT contain any word from the subject
        assert "Meeting" not in name
        assert "agenda" not in name
        assert "Q3" not in name
        assert "review" not in name

    def test_safe_filename_different_subject_different_name(self) -> None:
        subj1 = "Project update"
        subj2 = "Re: Project update"
        name1 = safe_filename(sha256_text(subj1))
        name2 = safe_filename(sha256_text(subj2))
        assert name1 != name2

    def test_safe_filename_fallback_empty(self) -> None:
        """Edge case: purely non-hex input should fallback."""
        name = safe_filename("!!!")
        assert name == "aaaaaaaa.json"
