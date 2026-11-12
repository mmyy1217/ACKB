#!/usr/bin/env python3
"""Index PTX ISA instruction and execution-model sections from one pinned NVIDIA manual.

The extractor reads a local HTML snapshot of the archived PTX ISA manual. It does
not download files, launch a compiler, or talk to a device. Manual prose stays out
of the repository: records keep anchors, short titles, mnemonics, and structured
target statements.
"""

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1"
ISA_VERSION = "9.4"
QUERY_TARGET = "sm_89"
SOURCE_DIR = Path("/home/zuomin/Projects/Compiler/work/experiments/ackb/ptx-index/source")

PINNED = {
    "html": {
        "name": "ptx-isa-13.4.3-index.html",
        "url": "https://docs.nvidia.com/cuda/archive/13.4.3/parallel-thread-execution/index.html",
        "bytes": 3928317,
        "sha256": "f1e14ad07468e26bf3724e41be86f3a68ab7914bcf0fc9824a6ad31a1eb2ec26",
    },
    "pdf": {
        "name": "ptx_isa_9.4.pdf",
        "url": "https://docs.nvidia.com/cuda/archive/13.4.3/pdf/ptx_isa_9.4.pdf",
        "bytes": 31078744,
        "sha256": "3851871026ca5bc81d85189cd3a70a2f9a9a4bb32208d927b3f0cd03c7b16e4e",
        "title_page": "PTX ISA Release 9.4, NVIDIA Corporation, Oct 12, 2026",
    },
    "gpus": {
        "name": "cuda-gpus.md",
        "url": "https://developer.nvidia.com/cuda/gpus.md",
        "page_url": "https://developer.nvidia.com/cuda/gpus",
        "bytes": 2604,
        "sha256": "864921385310f9ce7d9911db863aa75286e590e8658b502b0aff28a74ffc03b7",
    },
    "ada": {
        "name": "ada-tuning-guide-13.4.3.html",
        "url": "https://docs.nvidia.com/cuda/archive/13.4.3/ada-tuning-guide/index.html",
        "bytes": 22758,
        "sha256": "e86ba37e8db39f8863bc555572632d02280215f2e6f5cbbf3acd4685b70f1fcc",
    },
    "platform": {
        "name": "cuda-platform-13.4.3.html",
        "url": "https://docs.nvidia.com/cuda/archive/13.4.3/cuda-programming-guide/01-introduction/cuda-platform.html",
        "anchor": "compute-capability-and-streaming-multiprocessor-versions",
        "bytes": 43874,
        "sha256": "d65e5ba5b1ed1e559f16839c437ec81d715f60a14c18cdf1a76d638bd0d5fd2a",
    },
}

KNOWN_RUBRICS = {
    "Syntax",
    "Syntax (predefined)",
    "Description",
    "Semantics",
    "Notes",
    "PTX ISA Notes",
    "Target ISA Notes",
    "Examples",
    "Example",
    "Floating Point Notes",
    "Integer Notes",
    "Operands",
    "Qualifiers",
    "Release Notes",
    "Deprecation Note",
    "Removal Note",
    "Conditions",
    "References",
}
SM_TOKEN = r"sm_\d+[a-z]*"
SM_FIND = re.compile(SM_TOKEN)
VERSION_FIND = re.compile(r"\d+\.\d+")
SENTENCE_SPLIT = re.compile(r"(?<=\.)\s+")


def digest(value):
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def entry_id(anchor, number):
    payload = json.dumps(
        {"anchor": anchor, "isa": ISA_VERSION, "section": number},
        separators=(",", ":"),
        sort_keys=True,
    )
    return "ptx_" + digest(payload)[:24]


def collapse(value):
    return re.sub(r"\s+", " ", value).strip()


def normalize_sm(value):
    """Restore an omitted underscore in a token such as the manual's sm89."""
    return re.sub(r"\bsm(?=\d)", "sm_", value)


def fullmatch(pattern, text):
    return re.fullmatch(pattern, text, re.IGNORECASE)


def sm_parts(token):
    match = re.fullmatch(r"sm_(\d+)([a-z]*)", token)
    if not match:
        return None
    digits, suffix = match.group(1), match.group(2)
    if len(digits) <= 2:
        major = int(digits[0])
        minor = int(digits[1:]) if len(digits) > 1 else 0
    else:
        major = int(digits[:-1])
        minor = int(digits[-1])
    return major, minor, suffix


def cc_at_least(target, minimum):
    """Compare unsuffixed compute-capability order. Suffixed targets never match."""
    left = sm_parts(target)
    right = sm_parts(minimum)
    if not left or not right or left[2] or right[2]:
        return False
    return (left[0], left[1]) >= (right[0], right[1])


def same_family_at_least(target, minimum):
    left = sm_parts(target)
    right = sm_parts(minimum)
    if not left or not right:
        return False
    return left[0] == right[0] and left[2] == right[2] and left[1] >= right[1]


def judge_statement(statement, target_present):
    relation = statement["relation"]
    if relation in ("performance_note", "cross_reference", "legacy_target_limit", "advisory"):
        return "not_applicable"
    if relation == "excluded_minimum":
        return "no" if cc_at_least(QUERY_TARGET, statement["sm"]) else "yes"
    if relation == "all_architectures":
        return "yes" if target_present else "unknown"
    if relation == "exact_sm":
        names = [statement["sm"], *statement.get("aliases", [])]
        return "yes" if QUERY_TARGET in names else "no"
    if relation == "minimum_sm":
        if statement.get("same_family"):
            return "yes" if same_family_at_least(QUERY_TARGET, statement["sm"]) else "no"
        if sm_parts(statement["sm"])[2]:
            return "no"
        return "yes" if cc_at_least(QUERY_TARGET, statement["sm"]) else "no"
    return "unknown"


def support_from(statements, unparsed, deferred, target_present):
    """Combine per-statement verdicts.

    An exclusion on one subject overrides an older positive minimum for that
    same subject. An entry-scoped exclusion overrides every subject. Different
    subjects still mix into partial. Unparsed text stays unknown.
    """
    grouped = {}
    order = []
    entry_denied = False
    saw_unknown = False
    for statement in statements:
        applies = judge_statement(statement, target_present)
        statement["applies"] = applies
        if statement.get("scope") == "entry" and statement["relation"] == "excluded_minimum" and applies == "no":
            entry_denied = True
        if applies == "not_applicable":
            continue
        if applies == "unknown":
            saw_unknown = True
        subject = statement.get("subject")
        if subject not in grouped:
            order.append(subject)
            grouped[subject] = []
        grouped[subject].append((applies, statement["relation"]))
    if unparsed or saw_unknown:
        return "unknown"
    if entry_denied:
        return "documented_not_supported"
    collapsed = []
    for subject in order:
        pairs = grouped[subject]
        applies_list = [item[0] for item in pairs]
        excluded = any(relation == "excluded_minimum" and app == "no" for app, relation in pairs)
        if excluded:
            collapsed.append("no")
        elif "yes" in applies_list and "no" in applies_list:
            collapsed.append("partial")
        elif "yes" in applies_list:
            collapsed.append("yes")
        elif "no" in applies_list:
            collapsed.append("no")
    if not collapsed:
        return "unknown"
    if any(item == "partial" for item in collapsed):
        return "partial"
    if all(item == "no" for item in collapsed):
        return "documented_not_supported"
    if all(item == "yes" for item in collapsed) and not deferred:
        return "documented_supported"
    return "partial"


def fingerprint(text):
    collapsed = collapse(text)
    return {"sha256": digest(collapsed), "chars": len(collapsed)}


def parse_sm_requirement(rest):
    family = rest.endswith("in the same family")
    higher = "or higher" in rest
    core = re.sub(r"\s+or higher(?: in the same family)?$", "", rest).strip()
    tokens = SM_FIND.findall(core)
    if not tokens or re.sub(SM_TOKEN, "", core).strip(" ,or"):
        leftover = re.sub(SM_TOKEN, "", core)
        if collapse(leftover).strip(" ,or"):
            return None
    if not tokens:
        return None
    if higher:
        if len(tokens) != 1:
            return None
        return [{"relation": "minimum_sm", "sm": tokens[0], "same_family": family}]
    return [{"relation": "exact_sm", "sm": token, "same_family": False, "aliases": []} for token in tokens]


def parse_target_line(text):
    line = normalize_sm(collapse(text).strip()).rstrip(".:,")
    if not line or line.lower() == "note":
        return []
    if line.lower() in {
        "rounding modifiers have the following target requirements",
        "for .scale_vectorsize",
    }:
        return []
    require_header = fullmatch(r"(?P<subject>.+) require", line)
    if require_header:
        return [{
            "relation": "list_header",
            "subject": require_header.group("subject").rstrip(",").strip(),
            "scope": "architecture",
            "since_ptx": None,
        }]
    if re.fullmatch(r"\.[A-Za-z0-9_:.]+(?:\s*,\s*\.[A-Za-z0-9_:.]+)*", line):
        return []
    if line.startswith("For Target ISA details") or line.startswith("For Target ISA Note"):
        return [{"relation": "cross_reference"}]
    if "may have substantially reduced performance" in line:
        tokens = SM_FIND.findall(line)
        return [{"relation": "performance_note", "sm": tokens[0] if tokens else None}]
    legacy = re.fullmatch(
        r"Only (?P<subject>.+) is supported for (?P<sm>sm_\d+x?) targets",
        line,
    )
    if legacy:
        return [{
            "relation": "legacy_target_limit",
            "subject": legacy.group("subject"),
            "sm": legacy.group("sm"),
        }]
    compound = fullmatch(
        rf"(?P<subject>.+?) (?:requires|require) (?P<exact>{SM_TOKEN}) and "
        rf"(?:is|are) supported on (?P<family>{SM_TOKEN})"
        rf"(?P<higher> or higher in the same family| and later generation targets in the same family)?"
        rf" from PTX ISA version (?P<ver>\d+\.\d+)"
        rf"(?: except (?P<except>.+))?",
        line,
    )
    if compound:
        subject = compound.group("subject")
        if compound.group("except"):
            subject = subject + " except " + compound.group("except")
        family_relation = "minimum_sm" if compound.group("higher") else "exact_sm"
        return [
            {"relation": "exact_sm", "subject": subject, "sm": compound.group("exact"), "aliases": []},
            {
                "relation": family_relation,
                "subject": subject,
                "sm": compound.group("family"),
                "same_family": bool(compound.group("higher")),
                "since_ptx": compound.group("ver"),
                "aliases": [],
            },
        ]
    if "advised to be used with" in line.lower():
        tokens = SM_FIND.findall(line)
        return [{"relation": "advisory", "sm": token} for token in tokens] or [{"relation": "advisory"}]
    header = fullmatch(
        r"(?:(?P<subject>.+?) (?:is |are )?)?[Ss]upported on (?:the )?following "
        r"(?P<family>family-specific )?architectures"
        r"(?: from PTX ISA version (?P<ver>\d+\.\d+))?",
        line,
    )
    if header and "all target" not in line:
        return [{
            "relation": "list_header",
            "subject": header.group("subject"),
            "scope": "family" if header.group("family") else "architecture",
            "since_ptx": header.group("ver"),
        }]
    continued = fullmatch(
        r"And (?:is|are) supported on following (?P<family>family-specific )?architectures"
        r"(?: from PTX ISA version (?P<ver>\d+\.\d+))?(?: except .+)?",
        line,
    )
    if continued:
        return [{
            "relation": "list_header",
            "subject": None,
            "scope": "family" if continued.group("family") else "architecture",
            "since_ptx": continued.group("ver"),
        }]
    conditional = fullmatch(
        rf"(?P<sm>{SM_TOKEN}) when (?P<cond>.+) and is supported on (?P<other>{SM_TOKEN}) "
        rf"from PTX ISA version (?P<ver>\d+\.\d+)",
        line,
    )
    if conditional:
        condition = "when " + conditional.group("cond")
        return [
            {"relation": "exact_sm", "subject": condition, "sm": conditional.group("sm"), "aliases": []},
            {
                "relation": "exact_sm",
                "subject": condition,
                "sm": conditional.group("other"),
                "since_ptx": conditional.group("ver"),
                "aliases": [],
            },
        ]
    conditional_min = fullmatch(
        rf"(?P<sm>{SM_TOKEN}) or higher when (?P<cond>.+)",
        line,
    )
    if conditional_min:
        return [{
            "relation": "minimum_sm",
            "subject": "when " + conditional_min.group("cond"),
            "sm": conditional_min.group("sm"),
            "same_family": False,
        }]
    item = fullmatch(
        rf"(?P<sm>{SM_TOKEN})(?: or higher(?P<family> in the same family)?)?"
        rf"(?: \((?:Renamed to (?P<alias>{SM_TOKEN}) from PTX ISA version (?P<ver>\d+\.\d+)"
        rf"|refer to section for restrictions on {SM_TOKEN})\))?",
        line,
    )
    if item:
        if item.group("family") or "or higher" in line:
            return [{
                "relation": "minimum_sm",
                "sm": item.group("sm"),
                "same_family": bool(item.group("family")),
                "aliases": [],
            }]
        return [{
            "relation": "exact_sm",
            "sm": item.group("sm"),
            "aliases": [item.group("alias")] if item.group("alias") else [],
            "since_ptx": item.group("ver"),
        }]
    match = fullmatch(r"(?:(?P<subject>.+?) (?:is |are )?)?supported on all target architectures", line)
    if match:
        return [{"relation": "all_architectures", "subject": match.group("subject")}]
    plain_all = fullmatch(r"(?P<subject>.+?) supported on all target architectures", line)
    if plain_all:
        return [{"relation": "all_architectures", "subject": plain_all.group("subject")}]
    if line in ("available for all targets", "Available for all targets"):
        return [{"relation": "all_architectures", "subject": None}]
    available = fullmatch(r"(?P<subject>.+?) available for all targets", line)
    if available:
        return [{"relation": "all_architectures", "subject": available.group("subject")}]
    negative = fullmatch(
        r"(?P<subject>.+) is not supported on (?P<sm>sm_\d+[a-z]*) or higher"
        r"(?: starting PTX ISA version (?P<ver>\d+\.\d+))?",
        line,
    )
    if negative:
        return [{
            "relation": "excluded_minimum",
            "subject": negative.group("subject"),
            "sm": negative.group("sm"),
            "since_ptx": negative.group("ver"),
        }]
    mapped = fullmatch(
        rf"(?P<subject>.+) requires (?P<sm>{SM_TOKEN}) or higher, or \.target map_f64_to_f32",
        line,
    )
    if mapped:
        return [{
            "relation": "minimum_sm",
            "subject": mapped.group("subject"),
            "sm": mapped.group("sm"),
            "same_family": False,
        }]
    legacy_only = fullmatch(r"sm_1x targets support only the (?P<subject>.+)", line)
    if legacy_only:
        return [{"relation": "legacy_target_limit", "subject": legacy_only.group("subject"), "sm": "sm_1x"}]
    ignored = fullmatch(r"Ignored for (?P<sm>sm_\d+x?) targets", line)
    if ignored:
        return [{"relation": "legacy_target_limit", "subject": None, "sm": ignored.group("sm")}]
    required = fullmatch(
        r"(?:(?P<subject>.+?) )?(?:requires|require) (?:target |architecture )?(?P<rest>.+)",
        line,
    )
    if required:
        parsed = parse_sm_requirement(required.group("rest"))
        if parsed:
            for item in parsed:
                item["subject"] = required.group("subject")
            return parsed
    shaped = fullmatch(
        rf"(?P<subject>.+?) (?P<sm>{SM_TOKEN}) or higher(?P<family> in the same family)?",
        line,
    )
    if shaped and "requires" not in line and "require" not in line:
        return [{
            "relation": "minimum_sm",
            "subject": shaped.group("subject"),
            "sm": shaped.group("sm"),
            "same_family": bool(shaped.group("family")),
        }]
    parts = [part.strip() for part in SENTENCE_SPLIT.split(line) if part.strip()]
    if len(parts) > 1:
        combined = []
        for part in parts:
            parsed = parse_target_line(part)
            if parsed is None:
                return None
            combined.extend(parsed)
        return combined
    return None


def parse_target_blocks(blocks):
    statements = []
    unparsed = []
    pending = None
    deferred = False

    def close():
        nonlocal pending
        pending = None

    for block in blocks:
        parsed = parse_target_line(block)
        if parsed is None:
            close()
            unparsed.append(fingerprint(block))
            continue
        if any(item["relation"] == "list_header" for item in parsed):
            close()
            pending = parsed[0]
            continue
        if pending and parsed and all(item["relation"] in ("exact_sm", "minimum_sm") for item in parsed):
            for item in parsed:
                header_subject = pending.get("subject")
                own_subject = item.get("subject")
                if header_subject and own_subject:
                    item["subject"] = f"{header_subject} {own_subject}"
                elif header_subject:
                    item["subject"] = header_subject
                if pending.get("since_ptx") and "since_ptx" not in item:
                    item["since_ptx"] = pending["since_ptx"]
                if pending.get("scope") == "family" and item["relation"] == "minimum_sm":
                    item["same_family"] = True
            statements.extend(parsed)
            continue
        close()
        for item in parsed:
            if item["relation"] == "cross_reference":
                deferred = True
            statements.append(item)
    return statements, unparsed, deferred


PTX_SKIP = {
    "depending upon the ptx isa version, the parameter size limit varies",
    "the following table shows the allowed parameter size for a ptx isa version",
    "ptx isa version | maximum parameter size (in bytes)",
    "the cuda and opencl drivers support the following limits for parameter memory",
    "driver | parameter memory size",
}


def ptx_statement(kind, version, subject=None, **extra):
    if subject is not None:
        subject = collapse(subject)
        if len(subject) > 180:
            return None
    statement = {"kind": kind, "subject": subject, "version": version}
    statement.update(extra)
    return statement


def driver_parameter_limits(rest):
    found = re.findall(
        r"(\d+) bytes (?:for|fo|on) (sm_\d+x?)(?: (and higher|and lower))?",
        rest,
        re.IGNORECASE,
    )
    limits = []
    for size, sm, bound in found:
        limits.append({
            "bytes": int(size),
            "sm": sm,
            "bound": {"and higher": "minimum", "and lower": "maximum"}.get(bound.lower(), "exact"),
        })
    return limits


def parse_ptx_sentence(text):
    """Return statements, an empty list for a skipped header, or None if unparsed."""
    line = normalize_sm(collapse(text).strip()).rstrip(".")
    if not line:
        return []
    if line.lower().rstrip(":") in PTX_SKIP:
        return []
    renamed = fullmatch(r"\(Renamed to (?P<subject>sm_\d+[a-z]*)\)", line)
    if renamed:
        return [ptx_statement("renamed", None, renamed.group("subject"))]
    denied = fullmatch(
        rf"Not supported in PTX ISA version (?P<ver>\d+\.\d+) for \.target (?P<sm>{SM_TOKEN}) or higher",
        line,
    )
    if denied:
        return [ptx_statement("not_supported_on_target", denied.group("ver"), sm=denied.group("sm"))]
    typed = fullmatch(
        r"Introduced in PTX ISA version (?P<ver>\d+\.\d+) (?:with|as) type (?P<subject>.+)",
        line,
    )
    if typed:
        return [ptx_statement("introduced", typed.group("ver"), typed.group("subject"))]
    redefined = fullmatch(
        r"Redefined as (?P<subject>.+) in PTX ISA version (?P<ver>\d+\.\d+)",
        line,
    )
    if redefined:
        return [ptx_statement("redefined", redefined.group("ver"), redefined.group("subject"))]
    introduced = fullmatch(
        r"Introduced in PTX ISA version (?P<ver>\d+\.\d+)(?:(?:,| )(?P<tail>.+))?",
        line,
    )
    if introduced:
        return [ptx_statement("introduced", introduced.group("ver"), introduced.group("tail"))]
    added = fullmatch(
        r"(?:Support for )?(?P<subject>.+?) (?:introduced|were added|was added|added) in PTX ISA "
        r"(?:version )?(?P<ver>\d+\.\d+)(?: (?P<tail>.+))?",
        line,
    )
    if added:
        kind = "removed" if (added.group("tail") or "").startswith("has been removed") else "introduced"
        statement = ptx_statement(kind, added.group("ver"), added.group("subject"))
        return None if statement is None else [statement]
    deprecated = fullmatch(
        r"(?:(?P<subject>.+?) )?Deprecated (?:in|as of) PTX ISA version (?P<ver>\d+\.\d+)(?:(?:,| )(?P<tail>.+))?",
        line,
    )
    if deprecated:
        subject = deprecated.group("subject")
        if subject:
            subject = re.sub(r"\s+is$", "", subject)
        tail = deprecated.group("tail")
        first = ptx_statement("deprecated", deprecated.group("ver"), subject or tail)
        if first is None:
            return None
        removed_tail = fullmatch(r"and is removed from PTX ISA version (?P<ver>\d+\.\d+)", tail or "")
        if removed_tail:
            second = ptx_statement("removed", removed_tail.group("ver"), subject)
            return [first] if second is None else [first, second]
        return [first]
    removed = fullmatch(
        r"(?:(?P<subject>.+?) )?(?:Removed|removed) in PTX ISA version (?P<ver>\d+\.\d+)",
        line,
    )
    if removed:
        return [ptx_statement("removed", removed.group("ver"), removed.group("subject"))]
    clarified = fullmatch(
        r"(?P<subject>.+?) clarified in PTX ISA version (?P<ver>\d+\.\d+), "
        r"with retrospective effect from PTX ISA version (?P<prior>\d+\.\d+)",
        line,
    )
    if clarified:
        statement = ptx_statement(
            "clarified", clarified.group("ver"), clarified.group("subject"), also_version=clarified.group("prior"),
        )
        return None if statement is None else [statement]
    modifier = fullmatch(
        r"Modifier (?P<subject>.+?) is required from PTX ISA version (?P<ver>\d+\.\d+) onwards"
        r"(?:, and considered implicit in PTX ISA versions less than \d+\.\d+)?",
        line,
    )
    if modifier:
        return [ptx_statement("required_since", modifier.group("ver"), modifier.group("subject"))]
    supported_since = fullmatch(
        r"(?P<subject>.+?) is supported (?:in|from) PTX ISA version (?P<ver>\d+\.\d+) onwards",
        line,
    )
    if supported_since:
        statement = ptx_statement("introduced", supported_since.group("ver"), supported_since.group("subject"))
        return None if statement is None else [statement]
    requires_isa = fullmatch(
        r"(?P<subject>.+?) requires PTX ISA version (?P<ver>\d+\.\d+) or later",
        line,
    )
    if requires_isa:
        statement = ptx_statement("required_since", requires_isa.group("ver"), requires_isa.group("subject"))
        return None if statement is None else [statement]
    later = fullmatch(
        r"(?:For|In) PTX ISA versions? (?P<ver>\d+\.\d+) and later, (?P<subject>.+)",
        line,
    )
    if later:
        statement = ptx_statement("required_since", later.group("ver"), later.group("subject"))
        return None if statement is None else [statement]
    legacy_range = fullmatch(
        r"For PTX ISA versions (?P<start>\d+\.\d+) through (?P<ver>\d+\.\d+), (?P<subject>.+)",
        line,
    )
    if legacy_range:
        statement = ptx_statement(
            "legacy_range",
            legacy_range.group("ver"),
            legacy_range.group("subject"),
            since_version=legacy_range.group("start"),
        )
        return None if statement is None else [statement]
    parameter_row = fullmatch(
        r"PTX ISA version (?P<ver>\d+\.\d+) and above \| (?P<bytes>\d+)",
        line,
    )
    if parameter_row:
        return [ptx_statement(
            "parameter_limit", parameter_row.group("ver"), "normal parameters", bytes=int(parameter_row.group("bytes")),
        )]
    parameter_max = fullmatch(
        r"The maximum memory size supported by PTX for normal \(non-opaque type\) parameters is (?P<bytes>\d+) bytes",
        line,
    )
    if parameter_max:
        return [ptx_statement("parameter_limit", None, "normal parameters", bytes=int(parameter_max.group("bytes")))]
    driver = fullmatch(r"(?P<driver>CUDA|OpenCL) \| (?P<rest>.+)", line)
    if driver:
        limits = driver_parameter_limits(driver.group("rest"))
        if not limits:
            return None
        return [ptx_statement("driver_parameter_limit", None, driver.group("driver"), limits=limits)]
    legacy_read = fullmatch(
        r"For compatibility with legacy PTX code, (?P<width>16-bit(?: and 32-bit)?) mov and cvt instructions "
        r"may be used to read the lower (?P<bits>.+) of each component of %(?P<reg>[A-Za-z0-9_]+)",
        line,
    )
    if legacy_read:
        return [ptx_statement(
            "legacy_register_read",
            None,
            "%" + legacy_read.group("reg"),
            width=legacy_read.group("width"),
        )]
    mapped = fullmatch(
        r"Legacy (?P<subject>.+) instructions having no rounding modifier will map to (?P<to>\S+)",
        line,
    )
    if mapped:
        statement = ptx_statement("maps_to", None, mapped.group("subject"), maps_to=mapped.group("to"))
        return None if statement is None else [statement]
    reference = fullmatch(r"See the (?P<subject>.+) for details", line)
    if reference:
        statement = ptx_statement("cross_reference", None, reference.group("subject"))
        return None if statement is None else [statement]
    return None


def parse_ptx_blocks(blocks):
    statements = []
    unparsed = []
    for block in blocks:
        for sentence in SENTENCE_SPLIT.split(collapse(block)):
            parsed = parse_ptx_sentence(sentence)
            if parsed is None:
                unparsed.append(fingerprint(sentence.strip().rstrip(".")))
                continue
            for item in parsed:
                if item is None:
                    unparsed.append(fingerprint(sentence.strip().rstrip(".")))
                    continue
                if item["kind"] == "renamed" and statements and "renamed_to" not in statements[-1]:
                    statements[-1]["renamed_to"] = item["subject"]
                    continue
                statements.append(item)
    return statements, unparsed


def rubric_blocks(rubric):
    return [block for block in rubric["blocks"] if collapse(block)]


def rubric_text(rubric):
    return "\n".join(rubric_blocks(rubric))


class ManualParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.stack = []
        self.sections = []

    def handle_starttag(self, tag, attrs):
        attribute = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "section" and attribute.get("id"):
            parent = self.stack[-1]["id"] if self.stack else None
            frame = {
                "id": attribute["id"],
                "parent": parent,
                "number": "",
                "title_parts": [],
                "mnemonics": [],
                "heading": False,
                "in_number": False,
                "in_title": False,
                "in_title_code": False,
                "rubric": None,
                "rubrics": [],
                "in_pre": False,
                "in_cell": False,
                "row": [],
                "cell": [],
            }
            if self.stack:
                self.stack[-1].setdefault("child_ids", []).append(attribute["id"])
            self.stack.append(frame)
            self.sections.append(frame)
            return
        if not self.stack:
            return
        frame = self.stack[-1]
        classes = set((attribute.get("class") or "").split())
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not frame["number"]:
            frame["heading"] = True
            return
        if frame["heading"] and tag == "span" and "section-number" in classes:
            frame["in_number"] = True
            return
        if frame["heading"] and tag == "a" and "headerlink" not in classes:
            frame["in_title"] = True
            return
        if frame["in_title"] and tag == "code":
            frame["in_title_code"] = True
            frame["mnemonics"].append("")
            return
        if tag == "p" and "rubric" in classes and "rubric-h1" not in classes:
            self._finish_rubric(frame)
            frame["rubric"] = {"name": "", "blocks": [], "naming": True, "pre": []}
            return
        if tag == "pre":
            frame["in_pre"] = True
            if frame["rubric"] is not None:
                frame["rubric"]["pre"].append("")
            return
        if tag in ("li", "dt", "dd") or (tag == "p" and "rubric" not in classes):
            self._finish_paragraph(frame)
        if tag == "li":
            frame.setdefault("in_item", 0)
            frame["in_item"] = frame.get("in_item", 0) + 1
            if frame["rubric"] is not None and not frame["rubric"].get("naming"):
                frame["rubric"]["blocks"].append("")
                frame["rubric"]["paragraph_closed"] = False
            return
        if tag == "tr":
            frame["row"] = []
            return
        if tag in ("td", "th"):
            frame["in_cell"] = True
            frame["cell"] = []
            return
        if tag == "br" and frame["in_pre"] and frame["rubric"] and frame["rubric"]["pre"]:
            frame["rubric"]["pre"][-1] += "\n"

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
            return
        if self.skip or not self.stack:
            return
        frame = self.stack[-1]
        if tag == "section":
            self._finish_rubric(frame)
            frame["title"] = collapse("".join(frame["title_parts"]))
            frame["number"] = collapse(frame["number"])
            frame["mnemonics"] = [collapse(item) for item in frame["mnemonics"] if collapse(item)]
            self.stack.pop()
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and frame["heading"]:
            frame["heading"] = False
            frame["in_title"] = False
            return
        if tag == "span" and frame["in_number"]:
            frame["in_number"] = False
            return
        if tag == "a" and frame["in_title"]:
            frame["in_title"] = False
            return
        if tag == "code" and frame["in_title_code"]:
            frame["in_title_code"] = False
            return
        if tag == "p" and frame["rubric"] and frame["rubric"].get("naming"):
            frame["rubric"]["name"] = collapse(frame["rubric"]["name"])
            frame["rubric"]["naming"] = False
            return
        if tag == "p":
            self._finish_paragraph(frame)
            return
        if tag == "pre":
            frame["in_pre"] = False
            return
        if tag == "li" and frame.get("in_item"):
            frame["in_item"] -= 1
            return
        if tag in ("td", "th") and frame["in_cell"]:
            frame["row"].append(collapse("".join(frame["cell"])))
            frame["in_cell"] = False
            frame["cell"] = []
            return
        if tag == "tr" and frame["row"]:
            if frame["rubric"] is not None and not frame["rubric"].get("naming"):
                frame["rubric"]["blocks"].append(" | ".join(item for item in frame["row"] if item))
            frame["row"] = []

    def handle_data(self, data):
        if self.skip or not self.stack or not data:
            return
        frame = self.stack[-1]
        if frame["in_number"]:
            frame["number"] += data
            return
        if frame["in_title_code"]:
            frame["mnemonics"][-1] += data
            frame["title_parts"].append(data)
            return
        if frame["in_title"]:
            frame["title_parts"].append(data)
            return
        if frame["in_cell"]:
            frame["cell"].append(data)
            return
        rubric = frame["rubric"]
        if rubric is None or frame["heading"]:
            return
        if rubric.get("naming"):
            rubric["name"] += data
            return
        if frame["in_pre"] and rubric["pre"]:
            rubric["pre"][-1] += data
            return
        if frame.get("in_item") and rubric["blocks"]:
            rubric["blocks"][-1] += data
            return
        if not rubric["blocks"] or rubric.get("paragraph_closed"):
            rubric["blocks"].append(data)
            rubric["paragraph_closed"] = False
        else:
            rubric["blocks"][-1] += data

    def _finish_paragraph(self, frame):
        rubric = frame["rubric"]
        if rubric is not None and not rubric.get("naming"):
            rubric["paragraph_closed"] = True

    def _finish_rubric(self, frame):
        rubric = frame["rubric"]
        if rubric is None:
            return
        name = rubric["name"]
        if name.startswith("Examples of ") or name.startswith("Example of "):
            name = "Examples"
        rubric["name"] = name
        rubric["blocks"] = [collapse(block) for block in rubric["blocks"] if collapse(block)]
        rubric["pre"] = [item.strip("\n") for item in rubric["pre"] if item.strip()]
        frame["rubrics"].append(rubric)
        frame["rubric"] = None


def parse_manual(html):
    parser = ManualParser()
    parser.feed(html)
    return parser.sections


def ancestor_ids(section, by_id):
    result = []
    parent = section["parent"]
    while parent:
        result.append(parent)
        parent = by_id[parent]["parent"] if parent in by_id else None
    return result


def chapter(section):
    number = section["number"]
    return number.split(".", 1)[0] if number else ""


def has_rubric(section, names):
    return any(rubric["name"] in names for rubric in section["rubrics"])


def classify(section, ancestors):
    number = section["number"]
    top = chapter(section)
    in_instructions = "instructions" in ancestors or section["id"] == "instructions"
    noted = has_rubric(section, {"Target ISA Notes", "PTX ISA Notes", "Syntax", "Syntax (predefined)"})
    if in_instructions and section["id"] != "instructions":
        if has_rubric(section, {"Syntax", "Target ISA Notes"}):
            return "instruction"
        return "instruction_topic"
    if top == "10":
        return "special_register" if noted else "special_register_topic"
    if top in ("11", "12"):
        return "directive" if noted else "directive_topic"
    if top in ("2", "3", "8") or (top == "9" and not number.startswith("9.7")):
        return "execution_model"
    if number.startswith("5.1"):
        return "state_space"
    if top == "1":
        return "introduction"
    if top == "13":
        return "release_note"
    if top == "14":
        return "notice"
    return "other"


def public_statement(statement):
    subject = statement.get("subject")
    if isinstance(subject, str):
        subject = subject.rstrip(",").strip() or None
    result = {
        "relation": statement["relation"],
        "subject": subject,
        "sm": statement.get("sm"),
        "same_family": bool(statement.get("same_family")),
        "since_ptx": statement.get("since_ptx"),
        "aliases": statement.get("aliases") or [],
    }
    if statement.get("scope"):
        result["scope"] = statement["scope"]
    return result


def note_record(section, target_present):
    rubrics = {rubric["name"]: rubric for rubric in section["rubrics"]}
    target = rubrics.get("Target ISA Notes")
    ptx = rubrics.get("PTX ISA Notes")
    syntax = rubrics.get("Syntax") or rubrics.get("Syntax (predefined)")
    description = rubrics.get("Description")
    if target:
        statements, unparsed, deferred = parse_target_blocks(rubric_blocks(target))
    else:
        statements, unparsed, deferred = [], [fingerprint("missing Target ISA Notes")], False
    ptx_statements, ptx_unparsed = parse_ptx_blocks(rubric_blocks(ptx)) if ptx else ([], [fingerprint("missing PTX ISA Notes")])
    for item in ptx_statements:
        if item.get("kind") == "not_supported_on_target":
            statements.append({
                "relation": "excluded_minimum",
                "subject": None,
                "sm": item["sm"],
                "since_ptx": item["version"],
                "scope": "entry",
            })
    stored = [public_statement(item) for item in statements if item["relation"] != "list_header"]
    support = support_from(stored, unparsed, deferred, target_present)
    syntax_text = "\n".join(syntax["pre"]) if syntax else ""
    description_text = rubric_text(description) if description else ""
    return {
        "entry_id": entry_id(section["id"], section["number"]),
        "kind": None,
        "mnemonics": section["mnemonics"],
        "section_number": section["number"],
        "anchor": section["id"],
        "title": section["title"],
        "parent_anchor": section["parent"],
        "rubrics": [rubric["name"] for rubric in section["rubrics"]],
        "rubric_chars": {rubric["name"]: len(rubric_text(rubric)) for rubric in section["rubrics"]},
        "syntax": {
            "line_count": len([line for line in syntax_text.splitlines() if line.strip()]) if syntax else 0,
            "sha256": digest(syntax_text) if syntax else None,
        },
        "description": {
            "chars": len(description_text),
            "sha256": digest(description_text) if description else None,
        },
        "ptx_isa": {"statements": ptx_statements, "unparsed": ptx_unparsed},
        "target_isa": {"statements": stored, "unparsed": unparsed},
        "sm_89": {
            "support": support,
            "deferred_detail": deferred,
            "rule": "explicit_target_note_plus_numeric_cc_order",
        },
        "depth": "index",
        "compile_verification": "unverified",
        "runtime_verification": "unverified",
        "performance": "unverified",
        "experiments": [],
    }


def catalog_record(section, kind):
    return {
        "anchor": section["id"],
        "section_number": section["number"],
        "title": section["title"],
        "parent_anchor": section["parent"],
        "kind": kind,
        "child_count": len(section.get("child_ids", [])),
    }


def section_body(section, kind):
    return {
        "entry_id": entry_id(section["id"], section["number"]),
        "kind": kind,
        "section_number": section["number"],
        "anchor": section["id"],
        "title": section["title"],
        "parent_anchor": section["parent"],
        "rubrics": [rubric["name"] for rubric in section["rubrics"]],
        "child_count": len(section.get("child_ids", [])),
        "depth": "index",
        "text_stored": False,
        "compile_verification": "unverified",
        "runtime_verification": "unverified",
    }


def expand_targets(cell):
    found = []

    def brace(match):
        for part in match.group(1).split(","):
            found.append("sm_" + part.strip())
        return " "

    remainder = re.sub(r"sm_\{([^{}]+)\}", brace, cell)
    found.extend(SM_FIND.findall(remainder))
    return found


def parse_release_history(html):
    match = re.search(
        r'<table[^>]*id="release-notes-ptx-release-history"[\s\S]*?<tbody>([\s\S]*?)</tbody>',
        html,
    )
    if not match:
        raise ValueError("PTX release history table was not found")
    rows = []
    for row in re.findall(r"<tr[\s\S]*?</tr>", match.group(1)):
        cells = [collapse(re.sub(r"<[^>]+>", " ", cell)) for cell in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row)]
        cells = [cell for cell in cells if cell]
        if len(cells) < 3 or not cells[0].startswith("PTX ISA "):
            continue
        version = cells[0].replace("PTX ISA ", "", 1).strip()
        rows.append({
            "ptx_isa": version,
            "cuda_release": cells[1],
            "targets": expand_targets(cells[2]),
        })
    if not rows:
        raise ValueError("PTX release history table had no version rows")
    return rows


def parse_gpu_row(markdown):
    for line in markdown.splitlines():
        if line.startswith("| 8.9 |"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 3:
                raise ValueError("CUDA GPU table row 8.9 is incomplete")
            joined = " ".join(cells)
            return {
                "compute_capability": "8.9",
                "data_center": cells[1],
                "workstation_consumer": cells[2],
                "names_geforce_rtx_4080": "GeForce RTX 4080" in cells[2],
                "names_rtx_4080_laptop": "4080 Laptop" in joined or "4080 Laptop" in markdown,
            }
    raise ValueError("CUDA GPU table has no compute capability 8.9 row")


def check_ada(text):
    if not re.search(r"NVIDIA Ada</em> refers to devices of compute capability 8\.9", text):
        raise ValueError("Ada tuning guide does not define NVIDIA Ada as compute capability 8.9")


def check_platform(text):
    if "compute-capability-and-streaming-multiprocessor-versions" not in text:
        raise ValueError("CUDA programming guide is missing the SM version section")
    if "sm_120" not in text or "CC 12.0" not in text:
        raise ValueError("CUDA programming guide is missing the CC 12.0 / sm_120 example")


def require_pin(path, pin, binary=False):
    data = path.read_bytes()
    actual = digest(data)
    if len(data) != pin["bytes"] or actual != pin["sha256"]:
        raise ValueError(f"{path} does not match the pinned {pin['name']} hash")
    if binary and not data.startswith(b"%PDF-"):
        raise ValueError(f"{path} is not a PDF")
    return data


DEPTH_NOTES = [
    {
        "id": "note_execution_hierarchy",
        "title": "执行层级",
        "topic": "execution_hierarchy",
        "body": "PTX 把一次 kernel 组织成 grid。grid 由 CTA 组成，也可以由若干 CTA 组成的 cluster 组成；CTA 对应 CUDA 的 thread block，cluster 对应 thread block cluster。一个 CTA 内的线程可以互相通信。手册写明 cluster 这一级只适用于 sm_90 及更高的目标，所以 sm_89 不能沿用 cluster 的同步和跨 CTA shared 通信。warp 在手册里是机器相关常数，通常为 32 个线程，这里不把它写成这张笔记本 GPU 的测量值。SM 用 SIMT 把线程映射到标量核。Volta 起的 Independent Thread Scheduling 给每个线程单独的程序计数器和调用栈，线程可以在比 warp 更细的粒度上分叉再汇合。控制流构造默认按分歧处理，除非指令带 .uni。这些都是手册对执行模型的陈述，不是 RTX 4080 Laptop 上的占用率或调度实验。",
        "citations": [
            {"anchor": "thread-hierarchy", "section": "2.2"},
            {"anchor": "cooperative-thread-arrays", "section": "2.2.1"},
            {"anchor": "cluster-of-cooperative-thread-arrays", "section": "2.2.2"},
            {"anchor": "set-of-simt-multiprocessors", "section": "3.1"},
            {"anchor": "independent-thread-scheduling", "section": "3.2"},
            {"anchor": "divergence-of-threads-in-control-constructs", "section": "9.5"},
        ],
        "unknowns": [
            "官方 CUDA GPU 表没有名为 RTX 4080 Laptop 的行，本条不把笔记本 SKU 自动等同于表上的 GeForce RTX 4080。",
            "warp 宽度是否在 sm_89 上恒为 32，手册只说通常如此，本索引没有设备测量。",
            "Independent Thread Scheduling 的段落写的是 Volta 及之后，没有单独点名 sm_89。",
        ],
    },
    {
        "id": "note_state_spaces",
        "title": "状态空间",
        "topic": "state_spaces",
        "body": "手册用状态空间区分存储的地址可否取得、能否初始化、读写权限，以及在线程之间共享到哪一层。表里列出的名字是 .reg、.sreg、.const、.global、.local、.param、.shared 和已弃用的 .tex。寄存器没有完整地址，数量随平台变化，超出后会溢出到内存并改变性能；具体寄存器上限不在这一节给出。shared 指令不写子限定符时默认是 ::cta，也就是当前 CTA 的窗口；::cluster 才指向 cluster 里其他 CTA 的 shared 窗口。表 7 把 .shared 的共享写成 per-cluster，脚注说明拥有该内存的 CTA 以及 cluster 中其他仍活跃的 CTA 可以看见它。这是状态空间模型本身的句子。cluster 级是否可用，要另看执行层级那一节：只适用于 sm_90 及更高目标。因此不能从表上的 per-cluster 推出 sm_89 已经具备跨 CTA shared。静态分配的 shared 在这一节写明每 CTA 最多 48KB，放宽容量的目标列表是 sm_90a、sm_100a 等，其中没有 sm_89。",
        "citations": [
            {"anchor": "state-spaces", "section": "5.1"},
            {"anchor": "register-state-space", "section": "5.1.1"},
            {"anchor": "shared-state-space", "section": "5.1.7"},
            {"anchor": "cluster-of-cooperative-thread-arrays", "section": "2.2.2"},
        ],
        "unknowns": [
            "sm_89 上如果写出 .shared::cluster，编译器会拒绝、忽略还是降级，本索引没有编译实验。",
            "48KB 静态上限之外，驱动或 CUDA 运行时是否对 sm_89 另有 carveout，不属于这几节 PTX 正文，这里不补。",
        ],
    },
    {
        "id": "note_synchronization",
        "title": "同步与内存次序",
        "topic": "synchronization",
        "body": "bar 和 barrier 在一个 CTA 内同步，每个 CTA 有编号 0 到 15 的 barrier。参与线程数必须是 warp size 的倍数；不写线程数时，sync 形式等待 CTA 内线程，arrive 形式则必须给出非零线程数。PTX ISA 7.8 给这些指令加了 .cta。bar.warp.sync 的目标说明是 sm_30 或更高，按计算能力数值比较可以覆盖 sm_89，这仍只是手册语句。barrier.cluster 的目标说明是 sm_90 或更高，不覆盖 sm_89。membar.cta 和 membar.gl 写成所有目标架构都支持，membar.sys 要求 sm_20 或更高，fence 要求 sm_70 或更高；.cluster、fence.proxy.async 以及若干 proxy 限定符要求 sm_90 或更高，fabric 方向的限定符要求 sm_100 或更高。同一条 membar/fence 因此不能整条标成 sm_89 全部可用。mbarrier.init 要求 sm_80 或更高，其中 .layout 要求 sm_90 或更高。第 8 章是内存一致性模型的位置，本索引只保留章节锚点，不改写其中的次序公理，也没有做可见性实验。",
        "citations": [
            {"anchor": "parallel-synchronization-and-communication-instructions-bar", "section": "9.7.15.1"},
            {"anchor": "parallel-synchronization-and-communication-instructions-bar-warp-sync", "section": "9.7.15.2"},
            {"anchor": "parallel-synchronization-and-communication-instructions-barrier-cluster", "section": "9.7.15.3"},
            {"anchor": "parallel-synchronization-and-communication-instructions-membar", "section": "9.7.15.4"},
            {"anchor": "parallel-synchronization-and-communication-instructions-mbarrier-init", "section": "9.7.15.16.12"},
            {"anchor": "memory-consistency-model", "section": "8"},
        ],
        "unknowns": [
            "sm_30 or higher 这类句子没有在 sm_89 上用编译器核对过每一种 bar 形式。",
            "fence 的限定符必须按 Target ISA Notes 里的句子分别判断，不能合成一个布尔值。",
            "第 8 章的 scope 与第 9 章指令限定符如何逐条对应，本索引没有做人工对齐之外的证明。",
        ],
    },
    {
        "id": "note_selected_instruction_constraints",
        "title": "若干指令在 sm_89 上的边界",
        "topic": "instruction_constraints",
        "body": "手册收录一条指令，只说明 PTX ISA 9.4 描述了它，不说明 sm_89 可以实现它的每一种形式。mma 的基线是 sm_70 或更高，但形状和类型另有下限：一批形状要求 sm_75 或 sm_80，f64 的 m16n8k4、m16n8k8 和 m16n8k16 要求 sm_90 或更高，e4m3 与 e5m2 要求 sm_89 或更高。e3m2、e2m3、e2m1 以及 .kind、.block_scale、.scale_vec_size 要求 sm_120a，并在 PTX ISA 8.8 起的 sm_120f 同族上另有支持，其中没有 sm_89。wgmma 异步矩阵指令的目标说明是 sm_90a，不是 sm_89。tcgen05.mma 列出的是 sm_100a、sm_101a 和 sm_100f 这一族等目标，没有 sm_89。cvt 里针对 sm_89 的 FP8 形式在 PTX ISA Notes 中单独写了引入版本，不能从 cvt 这个名字推出全部浮点格式。ISA 9.4 的发布表仍然把 sm_89 列在可写目标里；同一版新加的 sm_107 与 tcgen05 扩展并不因此落到 sm_89。m8n8k4 有一条性能注释，说它为 sm_70 优化、在其他目标上可能明显变慢，这不是不支持声明。",
        "citations": [
            {"anchor": "warp-level-matrix-instructions-mma", "section": "9.7.16.5.14"},
            {"anchor": "asynchronous-warpgroup-level-matrix-instructions-wgmma-mma", "section": "9.7.17.5.2"},
            {"anchor": "tcgen05-mma-instructions-mma", "section": "9.7.18.10.10.1"},
            {"anchor": "data-movement-and-conversion-instructions-cvt", "section": "9.7.10.24"},
            {"anchor": "ptx-isa-version-9-4", "section": "1.3"},
            {"anchor": "release-notes", "section": "13"},
        ],
        "unknowns": [
            "没有在 sm_89 上编译或运行 mma、wgmma、tcgen05 或 cvt 的各种形式。",
            "wgmma 与 tcgen05 的锚点以抽取结果为准；若手册把某一变体拆到相邻小节，支持状态以该小节的 Target ISA Notes 为准。",
            "性能注释没有给出 sm_89 的周期或吞吐量。",
        ],
    },
]


def attach_note_status(notes):
    for note in notes:
        note["depth"] = "selected"
        note["compile_verification"] = "unverified"
        note["runtime_verification"] = "unverified"
        note["performance"] = "unverified"
        note["experiments"] = []
        note["language"] = "zh"
    return notes


def build_index(html):
    if "PTX ISA 9.4" not in html[:5000] and "<title>" in html and "PTX ISA 9.4" not in html:
        raise ValueError("HTML title is not PTX ISA 9.4")
    sections = parse_manual(html)
    by_id = {section["id"]: section for section in sections}
    history = parse_release_history(html)
    current = next((row for row in history if row["ptx_isa"] == ISA_VERSION), None)
    if current is None or QUERY_TARGET not in current["targets"]:
        raise ValueError("Release history does not list sm_89 for PTX ISA 9.4")
    target_present = True
    catalog = []
    instructions = []
    execution = []
    directives = []
    special_registers = []
    for section in sections:
        ancestors = ancestor_ids(section, by_id)
        kind = classify(section, ancestors)
        catalog.append(catalog_record(section, kind))
        if kind == "instruction":
            record = note_record(section, target_present)
            record["kind"] = kind
            instructions.append(record)
        elif kind == "special_register" and has_rubric(section, {"Target ISA Notes", "PTX ISA Notes"}):
            record = note_record(section, target_present)
            record["kind"] = kind
            special_registers.append(record)
        elif kind == "directive" and has_rubric(section, {"Target ISA Notes", "PTX ISA Notes", "Syntax"}):
            record = note_record(section, target_present)
            record["kind"] = kind
            directives.append(record)
        elif kind in ("execution_model", "state_space"):
            execution.append(section_body(section, kind))
    return {
        "sections": sections,
        "catalog": catalog,
        "instructions": instructions,
        "execution": execution,
        "directives": directives,
        "special_registers": special_registers,
        "history": history,
    }


def count_by(items, key):
    counts = {}
    for item in items:
        value = item[key] if isinstance(item, dict) else item
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def noted_records(built):
    return built["instructions"] + built["directives"] + built["special_registers"]


SUPPORT_STATES = (
    "documented_supported",
    "documented_not_supported",
    "partial",
    "unknown",
)


def support_counts(records):
    counts = {name: 0 for name in SUPPORT_STATES}
    for item in records:
        counts[item["sm_89"]["support"]] += 1
    return counts


def scan_report(built):
    kinds = count_by(built["catalog"], "kind")
    noted = noted_records(built)
    supports = support_counts(noted)
    instruction_supports = support_counts(built["instructions"])
    return {
        "html_sections": len(built["catalog"]),
        "kinds": kinds,
        "kind_total": sum(kinds.values()),
        "instructions": len(built["instructions"]),
        "execution_sections": len(built["execution"]),
        "directives_with_notes": len(built["directives"]),
        "special_registers_with_notes": len(built["special_registers"]),
        "sm_89_support": supports,
        "instruction_sm_89_support": instruction_supports,
        "unparsed_target_blocks": sum(len(item["target_isa"]["unparsed"]) for item in noted),
        "unparsed_ptx_isa_sentences": sum(len(item["ptx_isa"]["unparsed"]) for item in noted),
        "release_rows": len(built["history"]),
        "text_stored": False,
    }


def source_document(history, gpu_row):
    introduced = next(row for row in history if row["ptx_isa"] == "7.8")
    current = next(row for row in history if row["ptx_isa"] == ISA_VERSION)
    return {
        "protocol": "ptx-index.v1",
        "extractor_revision": REVISION,
        "isa": {
            "name": "PTX ISA",
            "version": ISA_VERSION,
            "cuda_archive": "13.4.3",
            "cuda_release_row": current["cuda_release"],
            "pdf": PINNED["pdf"],
            "html": PINNED["html"],
            "html_role": "section anchors and instruction metadata",
            "pdf_role": "pinned manual checked from its title page; the extractor hashes it and does not parse PDF text",
        },
        "query_target": {
            "requested_name": "RTX 4080 Laptop",
            "requested_label": "Ada",
            "ptx_target": QUERY_TARGET,
            "isa_version_is_not_the_target": True,
            "compile_verification": "unverified",
            "runtime_verification": "unverified",
            "experiments": [],
            "sku_evidence": {
                "cuda_gpu_table": {
                    "url": PINNED["gpus"]["page_url"],
                    "markdown_url": PINNED["gpus"]["url"],
                    "sha256": PINNED["gpus"]["sha256"],
                    "row": gpu_row,
                },
                "ada_tuning_guide": {
                    "url": PINNED["ada"]["url"],
                    "sha256": PINNED["ada"]["sha256"],
                    "fact": "This guide defines NVIDIA Ada as devices of compute capability 8.9.",
                },
                "sm_naming": {
                    "url": PINNED["platform"]["url"] + "#" + PINNED["platform"]["anchor"],
                    "sha256": PINNED["platform"]["sha256"],
                    "fact": "The programming guide says compute capability X.Y corresponds to the SM version. Its example is CC 12.0 and sm_120, so CC 8.9 names sm_89. That naming rule does not identify the laptop SKU.",
                },
            },
        },
        "release_history": {
            "table_anchor": "release-notes-ptx-release-history",
            "sm_89_introduced": introduced,
            "isa_9_4": current,
        },
        "support_rule": {
            "id": "explicit_target_note_plus_numeric_cc_order",
            "summary": "sm_89 support is judged only from Target ISA Notes. Unsuffixed 'sm_X or higher' uses compute-capability order. Same-family wording stays inside that major version and suffix. Architecture lists and suffixed targets such as sm_90a match only when sm_89 is named. Unparsed sentences force unknown. No statement is filled in from the instruction name.",
        },
        "limits": [
            "The HTML snapshot and the PDF are sibling files of CUDA archive 13.4.3. Anchors come from the HTML. The PDF was read at its title page and hashed; PDF pages are not the extraction input.",
            "Numeric comparison of 'or higher' is an index rule grounded in the programming guide's CC-to-SM numbering and the note's wording. It is not a device run.",
            "The official GPU table names GeForce RTX 4080 at CC 8.9 and does not name RTX 4080 Laptop.",
            "Compile, runtime, and performance states stay unverified.",
            "Two PTX ISA Note sentences stay as sha256 fingerprints: a usage constraint on kernel-function addresses, and an implementation caveat about generic pointers to const space. They do not change sm_89 support.",
        ],
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assemble_outputs(html, gpu_markdown, ada_html, platform_html):
    check_ada(ada_html)
    check_platform(platform_html)
    gpu_row = parse_gpu_row(gpu_markdown)
    built = build_index(html)
    notes = attach_note_status(json.loads(json.dumps(DEPTH_NOTES)))
    anchors = {item["anchor"]: item["section_number"] for item in built["catalog"]}
    for note in notes:
        missing = [item["anchor"] for item in note["citations"] if item["anchor"] not in anchors]
        if missing:
            raise ValueError("depth note cites missing anchors: " + ", ".join(missing))
        mismatched = [
            f"{item['anchor']} expected {item['section']} found {anchors[item['anchor']]}"
            for item in note["citations"]
            if anchors[item["anchor"]].rstrip(".") != item["section"].rstrip(".")
        ]
        if mismatched:
            raise ValueError("depth note section numbers differ: " + "; ".join(mismatched))
    scan = scan_report(built)
    return {
        "source": source_document(built["history"], gpu_row),
        "scan": scan,
        "sections": built["catalog"],
        "instructions": built["instructions"],
        "execution": built["execution"],
        "directives": built["directives"],
        "special_registers": built["special_registers"],
        "notes": notes,
    }


def load_tree(directory):
    names = ["source", "scan", "sections", "instructions", "execution", "directives", "special_registers", "notes"]
    return {name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8")) for name in names}


def validate_tree(tree):
    errors = []
    scan = tree["scan"]
    if scan["html_sections"] != scan["kind_total"] or scan["html_sections"] != len(tree["sections"]):
        errors.append("section counts do not add up")
    if scan["instructions"] != len(tree["instructions"]):
        errors.append("instruction count does not match the scan")
    anchors = [item["anchor"] for item in tree["sections"]]
    if len(anchors) != len(set(anchors)):
        errors.append("duplicate section anchors")
    anchor_set = set(anchors)
    allowed = set(SUPPORT_STATES)
    leaked = []
    observed = {name: 0 for name in SUPPORT_STATES}
    unparsed_target = 0
    unparsed_ptx = 0
    for record in tree["instructions"] + tree["directives"] + tree["special_registers"]:
        support = record["sm_89"]["support"]
        if support in observed:
            observed[support] += 1
        if support not in allowed:
            errors.append(f"bad support on {record['anchor']}")
        if record["compile_verification"] != "unverified" or record["runtime_verification"] != "unverified":
            errors.append(f"verification was upgraded on {record['anchor']}")
        if record["experiments"]:
            errors.append(f"experiment recorded without evidence on {record['anchor']}")
        unparsed_target += len(record["target_isa"]["unparsed"])
        unparsed_ptx += len(record["ptx_isa"]["unparsed"])
        blob = json.dumps(record, ensure_ascii=False)
        if "SECRET" in blob or len(blob) > 200000:
            leaked.append(record["anchor"])
        for value in json.dumps(record["target_isa"]).split('"'):
            if len(value) > 240:
                leaked.append(record["anchor"])
    if leaked:
        errors.append("manual prose or overlong fields in " + ", ".join(sorted(set(leaked))[:8]))
    if scan["unparsed_target_blocks"] != unparsed_target:
        errors.append("unparsed target count does not match records")
    if scan["unparsed_ptx_isa_sentences"] != unparsed_ptx:
        errors.append("unparsed PTX ISA count does not match records")
    noted = len(tree["instructions"]) + len(tree["directives"]) + len(tree["special_registers"])
    if sum(scan["sm_89_support"].values()) != noted or scan["sm_89_support"] != observed:
        errors.append("sm_89 support counts do not match records")
    if sum(scan["instruction_sm_89_support"].values()) != len(tree["instructions"]):
        errors.append("instruction support counts do not match records")
    if sum(count for name, count in observed.items() if name != "documented_supported") == 0:
        errors.append("sm_89 support collapsed to supported")
    for note in tree["notes"]:
        if note["experiments"] or note["compile_verification"] != "unverified":
            errors.append(f"note {note['id']} claims an experiment")
        for citation in note["citations"]:
            if citation["anchor"] not in anchor_set:
                errors.append(f"note {note['id']} misses {citation['anchor']}")
        if not note["unknowns"]:
            errors.append(f"note {note['id']} has no unknowns")
    history = tree["source"]["release_history"]
    if "sm_89" not in history["sm_89_introduced"]["targets"] or history["sm_89_introduced"]["ptx_isa"] != "7.8":
        errors.append("sm_89 introduction row is wrong")
    if "sm_89" not in history["isa_9_4"]["targets"] or history["isa_9_4"]["ptx_isa"] != "9.4":
        errors.append("ISA 9.4 target list lost sm_89")
    if tree["source"]["query_target"]["sku_evidence"]["cuda_gpu_table"]["row"]["names_rtx_4080_laptop"]:
        errors.append("GPU table was interpreted as naming the laptop SKU")
    if tree["source"]["isa"]["version"] == tree["source"]["query_target"]["ptx_target"]:
        errors.append("ISA version and sm target were collapsed")
    return errors


def extract(html_path, pdf_path, gpus_path, ada_path, platform_path, output):
    require_pin(html_path, PINNED["html"])
    require_pin(pdf_path, PINNED["pdf"], binary=True)
    gpus = require_pin(gpus_path, PINNED["gpus"]).decode()
    ada = require_pin(ada_path, PINNED["ada"]).decode()
    platform = require_pin(platform_path, PINNED["platform"]).decode()
    html = html_path.read_text(encoding="utf-8")
    tree = assemble_outputs(html, gpus, ada, platform)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("source", "scan", "sections", "instructions", "execution", "directives", "special_registers", "notes"):
        write_json(output / f"{name}.json", tree[name])
    errors = validate_tree(tree)
    if errors:
        raise ValueError("; ".join(errors))
    return tree["scan"]


def main():
    parser = argparse.ArgumentParser(description="Build or check the pinned PTX ISA index")
    sub = parser.add_subparsers(dest="command", required=True)
    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("--html", type=Path, default=SOURCE_DIR / PINNED["html"]["name"])
    extract_parser.add_argument("--pdf", type=Path, default=SOURCE_DIR / PINNED["pdf"]["name"])
    extract_parser.add_argument("--gpus", type=Path, default=SOURCE_DIR / PINNED["gpus"]["name"])
    extract_parser.add_argument("--ada", type=Path, default=SOURCE_DIR / PINNED["ada"]["name"])
    extract_parser.add_argument("--platform", type=Path, default=SOURCE_DIR / PINNED["platform"]["name"])
    extract_parser.add_argument("--output", type=Path, default=ROOT / "data/ptx")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--data", type=Path, default=ROOT / "data/ptx")
    args = parser.parse_args()
    if args.command == "extract":
        scan = extract(args.html, args.pdf, args.gpus, args.ada, args.platform, args.output)
        print(json.dumps(scan, indent=2, sort_keys=True))
        return
    errors = validate_tree(load_tree(args.data))
    if errors:
        raise SystemExit("\n".join(errors))
    print("ok")


if __name__ == "__main__":
    main()
