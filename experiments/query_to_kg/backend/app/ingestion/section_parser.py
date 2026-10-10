"""
    Rule based parser for splitting parsed paper text into sections., 
    
    This module turns one paper's parsed text into Sections objects.
    It  does not write JSON, create chunks , extract  KG data ,or mix papers.
"""

from pathlib import Path 
import re 


from backend.app.ingestion.schemas import Section 


COMMON_SECTION_TITLES = { 
    "abstract",
    "introduction",
    "related work",
    "background",
    "method",
    "methods",
    "methodology",
    "approach",
    "architecture",
    "experiments",
    "experimental setup",
    "results",
    "evaluation",
    "discussion",
    "conclusion",
    "conclusions",
    "limitations",
    "references",
    "appendix",
}

def build_section(
    paper_id: str,
    order: int,
    title: str,
    level: int,
    lines: list[str],
) -> Section | None:
    """Create a Section object if the collected text is non-empty."""
    text = "\n".join(lines).strip()

    if not text:
        return None

    return Section(
        section_id=make_section_id(paper_id, order),
        paper_id=paper_id,
        title=title,
        level=level,
        order=order,
        text=text,
    )

def parse_sections(paper_id: str, text: str) -> list[Section]:
    """
    Split one paper's parsed text into structured sections.

    Args:
        paper_id: Stable ID for the paper.
        text: Parsed text for exactly one paper.

    Returns:
        A list of Section objects.
    """
    if not paper_id.strip():
        raise ValueError("paper_id must not be empty")

    if not text.strip():
        raise ValueError(f"No parsed text provided for paper_id={paper_id}")

    sections: list[Section] = []

    current_title = "Preamble"
    current_level = 1
    current_lines: list[str] = []

    order = 1
    seen_first_heading = False

    for line in text.splitlines():
        detected = detect_heading(line)

        if detected is not None:
            # Save previous section before starting a new one.
            previous = build_section(
                paper_id=paper_id,
                order=order,
                title=current_title,
                level=current_level,
                lines=current_lines,
            )

            if previous is not None:
                sections.append(previous)
                order += 1

            current_title, current_level = detected
            current_lines = []
            seen_first_heading = True
            continue

        # Ignore tiny preamble noise before first real heading.
        if not seen_first_heading and not line.strip():
            continue

        current_lines.append(line)

    # Save final section.
    final_section = build_section(
        paper_id=paper_id,
        order=order,
        title=current_title,
        level=current_level,
        lines=current_lines,
    )

    if final_section is not None:
        sections.append(final_section)

    return sections


def parse_sections_from_file(paper_id: str, parsed_text_path: Path) -> list[Section]:
    """Load parsed text from disk and parse it into sections."""
    if not parsed_text_path.exists():
        raise FileNotFoundError(f"Parsed text file not found: {parsed_text_path}")

    text = parsed_text_path.read_text(encoding="utf-8")

    return parse_sections(paper_id=paper_id, text=text)

def detect_heading(line: str) -> tuple[str, int] | None:
    """
    Detect whether a line is a section heading.

    Returns:
        (clean_title, level) if the line looks like a heading.
        None otherwise.
    """
    stripped = line.strip()

    if not stripped:
        return None

    # Avoid treating long sentences as headings.
    if len(stripped) > 120:
        return None

    # Avoid figure/table captions.
    lowered = stripped.lower()
    if lowered.startswith(("figure ", "fig. ", "table ")):
        return None

    # Most headings are short.
    if len(stripped.split()) > 14:
        return None

    clean_title = normalize_heading_title(stripped)
    clean_lower = clean_title.lower()

    # Direct match: "Abstract", "Introduction", "References"
    if clean_lower in COMMON_SECTION_TITLES:
        return clean_title, infer_heading_level(stripped)

    # Appendix variants: "Appendix A", "Appendix B. Extra Results"
    if clean_lower.startswith("appendix"):
        return clean_title, infer_heading_level(stripped)

    # Numbered subsection with a known phrase:
    # "3.1 Experimental Setup", "4.2 Results"
    for known_title in COMMON_SECTION_TITLES:
        if clean_lower == known_title:
            return clean_title, infer_heading_level(stripped)

    return None

def normalize_heading_title(raw_title: str) -> str:
    """ Return a clean, human-readable section title."""

    title = raw_title.strip()


    # remove markdhow heading markers.
    title = re.sub(r"^#{1,6}\s*", "", title)

     # Remove leading numbering such as:
    # "1 Introduction", "1. Introduction", "3.2 Method", "III. Results"
    title = re.sub(
        r"^((\d+(\.\d+)*)|([IVXLC]+))\.?\s+",
        "",
        title,
        flags=re.IGNORECASE,
    )

    # Remove trailing colon.
    title = title.rstrip(":").strip()

    # Normalize internal whitespace.
    title = re.sub(r"\s+", " ", title)

    # Make all-caps headings readable.
    if title.isupper():
        title = title.title()

    return title



def make_section_id(paper_id: str, order: int) -> str:
    """Create a stable section ID scoped to one paper."""
    return f"{paper_id}_section_{order:03d}"


def infer_heading_level(line: str) -> int:
    """
    Infer section level from a numeric heading prefix.

    Examples:
    "1 Introduction" -> 1
    "3.2 Experiments" -> 2
    "4.1.2 Dataset" -> 3
    """
    stripped = line.strip()

    markdown_match = re.match(r"^(#{1,6})\s+", stripped)
    if markdown_match:
        return len(markdown_match.group(1))

    numeric_match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", stripped)
    if numeric_match:
        return numeric_match.group(1).count(".") + 1

    return 1



