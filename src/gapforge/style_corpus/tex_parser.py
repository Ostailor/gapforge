"""Small TeX parser for structural style features only."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

SECTION_RE = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]+)\}")
TITLE_RE = re.compile(r"\\title(?:\[[^\]]*\])?\{([^{}]+)\}", re.DOTALL)
ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL | re.IGNORECASE)
BEGIN_ENV_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}")
CITE_RE = re.compile(r"\\(?:cite|citet|citep|citealp|autocite|parencite|textcite)\*?(?:\[[^\]]*\])*\{([^{}]+)\}")
MACRO_RE = re.compile(r"\\(?:newcommand|renewcommand|providecommand)\*?(?:\{\\([A-Za-z@]+)\}|\\([A-Za-z@]+))")
DEF_RE = re.compile(r"\\def\\([A-Za-z@]+)")
WORD_RE = re.compile(r"[A-Za-z0-9]+")


def parse_tex_file(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = _strip_comments(raw)
    abstract = _first_match(ABSTRACT_RE, text)
    sections = [_clean_title(item) for item in SECTION_RE.findall(text)]
    word_count = len(WORD_RE.findall(text))
    citation_count = _citation_count(text)
    environments = Counter(BEGIN_ENV_RE.findall(text))
    return {
        "title": _clean_title(_first_match(TITLE_RE, text)) or path.stem.replace("_", " ").replace("-", " ").title(),
        "section_titles": sections,
        "macro_summary": _macro_summary(text),
        "environment_summary": dict(sorted(environments.items())),
        "citation_density": citation_count / word_count if word_count else 0.0,
        "figure_table_counts": {
            "figure": environments.get("figure", 0) + environments.get("figure*", 0),
            "table": environments.get("table", 0) + environments.get("table*", 0),
        },
        "abstract_length": len(WORD_RE.findall(abstract)),
        "contribution_statement_patterns": _contribution_patterns(text),
        "limitations_presence": _limitations_presence(sections, text),
    }


def _macro_summary(text: str) -> dict[str, int]:
    names = []
    for match in MACRO_RE.findall(text):
        names.append(next((item for item in match if item), "unknown"))
    names.extend(DEF_RE.findall(text))
    counter = Counter(names)
    return {
        "custom_macro_count": sum(counter.values()),
        "unique_custom_macro_count": len(counter),
        "newcommand_like_count": len(MACRO_RE.findall(text)),
        "def_count": len(DEF_RE.findall(text)),
    }


def _contribution_patterns(text: str) -> list[str]:
    lower = text.lower()
    patterns = []
    if re.search(r"\\section\*?\{[^{}]*contribution", lower):
        patterns.append("explicit_contributions_section")
    if re.search(r"\\begin\{itemize\}.*?(our contributions|we contribute|we propose|we introduce)", lower, re.DOTALL):
        patterns.append("contribution_bullets")
    if "we propose" in lower:
        patterns.append("we_propose_statement")
    if "we introduce" in lower:
        patterns.append("we_introduce_statement")
    if "we show" in lower or "we demonstrate" in lower:
        patterns.append("we_show_or_demonstrate_statement")
    if "benchmark" in lower and ("dataset" in lower or "protocol" in lower):
        patterns.append("benchmark_or_dataset_framing")
    return sorted(set(patterns))


def _limitations_presence(sections: list[str], text: str) -> bool:
    section_text = " ".join(sections).lower()
    return "limitation" in section_text or bool(re.search(r"\\section\*?\{[^{}]*(discussion|broader impact|ethics)", text, re.I))


def _citation_count(text: str) -> int:
    count = 0
    for match in CITE_RE.findall(text):
        keys = [key.strip() for key in match.split(",") if key.strip()]
        count += max(1, len(keys))
    return count


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("%"):
            continue
        lines.append(_strip_line_comment(line))
    return "\n".join(lines)


def _strip_line_comment(line: str) -> str:
    escaped = False
    for index, char in enumerate(line):
        if char == "\\" and not escaped:
            escaped = True
            continue
        if char == "%" and not escaped:
            return line[:index]
        escaped = False
    return line


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1) if match else ""


def _clean_title(value: str) -> str:
    cleaned = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", "", value)
    cleaned = cleaned.replace("{", "").replace("}", "")
    return " ".join(cleaned.split())
