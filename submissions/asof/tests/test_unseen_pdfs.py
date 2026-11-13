"""The SPR policy PDFs hold GPT's text word for word, as intake's own reader sees it.

The three PDFs are what SPR's onboarding uploads through Policy intake (asof/eval/unseen/onboard.py). If any of
them lost, gained or changed a word, the eval would be measuring AsOf on a policy GPT did not write."""

from __future__ import annotations

import hashlib
import io

import pytest
from pypdf import PdfReader

from asof import intake
from asof.eval.unseen import pdfs

# Pinned when the PDFs were committed; the onboarding records name these hashes (POLICY_DRAFT.SOURCE_SHA256).
PDF_SHA256 = {
    1: "6f7d1934bc52ee4b3b9ec70ee737fdf77c00e92934ab449008059dbd3944c900",
    2: "4b0b1823a2da36e1a47f3ea24215fce358763f804cb55839c1f52eaf846e1141",
    3: "b7cbc62aee95e10b65cac5c9c8979f79442f87d3ee9fb45990153faf631ba4a1",
}


@pytest.mark.parametrize("version", pdfs.VERSIONS)
def test_intakes_reader_gets_back_every_word_of_the_text_file(version):
    data = pdfs.pdf_path(version).read_bytes()
    text = pdfs.text_path(version).read_text(encoding="utf-8")
    source = intake.read_pdf(data, f"spr_policy_v{version}.pdf")
    # intake.read_pdf normalises (straight quotes and dashes, one space); so does the comparison, and nothing else.
    assert source.text.split() == intake.normalize(text).split()
    assert len(source.pages) == 2


@pytest.mark.parametrize("version", pdfs.VERSIONS)
def test_the_raw_text_layer_is_the_text_file_word_for_word(version):
    """Before any normalising: the em dashes, en dashes and curly apostrophe survive too."""
    reader = PdfReader(io.BytesIO(pdfs.pdf_path(version).read_bytes()))
    raw = "\n".join(page.extract_text() for page in reader.pages)
    assert raw.split() == pdfs.text_path(version).read_text(encoding="utf-8").split()


@pytest.mark.parametrize("version", pdfs.VERSIONS)
def test_the_committed_pdf_is_what_the_generator_makes_and_is_pinned(version):
    data = pdfs.pdf_path(version).read_bytes()
    assert data == pdfs.build(version)
    assert hashlib.sha256(data).hexdigest() == PDF_SHA256[version]


def test_a_long_line_is_wrapped_at_spaces_only():
    line = " ".join(f"word{i}" for i in range(60))
    out = pdfs.layout(line)
    assert len(out) > 1 and all(len(x) <= pdfs.WRAP_CHARS for x in out)
    assert " ".join(out).split() == line.split()


def test_a_character_winansi_cannot_show_is_refused_not_dropped():
    with pytest.raises(UnicodeEncodeError):
        pdfs.make_pdf("fare ≥ 48 h", "t")
