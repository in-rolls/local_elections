"""The transliteration stage's cleaning, suspect check and Muse path."""

from local_elections.tools import transliterate as T


def test_dashes_and_serials_are_not_part_of_the_name():
    assert T.clean("बसिया–") == "बसिया"
    assert T.clean("बारवाँ—") == "बारवाँ"
    assert T.clean("- नयाडीह") == "नयाडीह"


def test_an_invented_digit_is_suspect_but_a_printed_one_is_not():
    # indicate's misreading of अली
    assert T.suspect("वाजिद अली", "vajid 0lī") == "digit in the reading"
    assert T.suspect("मो ० रईस", "mo 00 rais") == "digit in the reading"
    assert T.suspect("કીમ-૨", "kim 2") == ""


def test_marks_that_are_not_words_cannot_be_lost():
    assert T.suspect("मो ० रईस", "mo rais") == ""
    assert T.suspect("मर्सोली - 1", "marsoli") == ""
    assert T.suspect("राम प्रसाद यादव", "ram yadav") == "lost 1 of 3 words"


def test_diacritics_are_stripped_from_a_reading():
    assert T.ascii_latin("  Rāmā   Dēvī ") == "rama devi"


class StubClient:
    model = "stub-model"

    def __init__(self):
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        rows = messages[1]["content"].splitlines()[1:]
        return {
            "results": [
                {"id": int(i), "latin": f"Name {i}"}
                for i, _ in (r.split("\t") for r in rows)
            ]
        }

    def spend(self):
        return {}


def test_muse_readings_are_paired_back_by_id_and_batched():
    client = StubClient()
    names = [f"नाम{i}" for i in range(T.MUSE_BATCH + 5)]
    got = T.by_muse(client, "devanagari", names)
    assert len(client.calls) == 2
    assert len(got) == len(names)
    first = sorted(names)[0]
    assert got[first][0] == "name 0"
    assert got[first][1] == f"stub-model reasoning=low prompt={T.MUSE_PROMPT_SHA}"
    assert "Hindi (Devanagari)" in client.calls[0][0]["content"]


def test_a_failed_batch_is_skipped_not_fatal():
    class Failing(StubClient):
        def complete(self, messages, **kwargs):
            raise RuntimeError("provider error")

    assert T.by_muse(Failing(), "tamil", ["அ", "ஆ"]) == {}


def test_a_request_that_runs_out_of_output_is_retried_in_halves():
    class Long(StubClient):
        def complete(self, messages, **kwargs):
            if len(messages[1]["content"].splitlines()) - 1 > T.MUSE_BATCH // 2:
                raise RuntimeError("incomplete response: finish_reason=length")
            return super().complete(messages, **kwargs)

    names = [f"நாம{i}" for i in range(T.MUSE_BATCH)]
    client = Long()
    assert len(T.by_muse(client, "tamil", names)) == len(names)
    assert len(client.calls) == 2
