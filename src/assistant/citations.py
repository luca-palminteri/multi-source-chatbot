"""Extract document and graph source IDs from individual or grouped markers."""
import re


def citation_ids(answer):
    groups = re.findall(r"\[([DG]\d+(?:\s*,\s*[DG]\d+)*)\]", answer)
    return {source for group in groups for source in re.findall(r"[DG]\d+", group)}
