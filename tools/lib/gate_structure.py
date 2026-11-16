"""Python AST checks and conservative JavaScript/TypeScript static checks."""
import ast
from pathlib import Path, PurePosixPath
import re

from .gate_config import compile_pattern
from .gate_git import CODE_EXTENSIONS


JAVASCRIPT = {".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx"}
TOKEN = re.compile(
    r"(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)"
    r"|(?P<string>\"(?:\\[\s\S]|[^\"\\])*\"|'(?:\\[\s\S]|[^'\\])*'|`(?:\\[\s\S]|[^`\\])*`)"
    r"|(?P<word>[$\w]+)|(?P<symbol>=>|[^\s])"
)
CONTROLS = {"if", "for", "while", "switch", "catch", "with", "synchronized"}


def _js_tokens(text):
    return [(match.lastgroup, match.group(), match.start())
            for match in TOKEN.finditer(text) if match.lastgroup != "comment"]


def _line(text, position):
    return text.count("\n", 0, position) + 1


def _function_open(tokens, index, parens):
    if index and tokens[index - 1][1] == "=>":
        return True
    closing = next((j for j in range(index - 1, -1, -1)
                    if tokens[j][1] in (")", ";", "{", "}")), -1)
    if closing < 0 or tokens[closing][1] != ")" or closing not in parens:
        return False
    opening = parens[closing]
    previous = tokens[opening - 1][1] if opening else ""
    if previous in CONTROLS:
        return False
    if previous == "function" or (opening > 1 and tokens[opening - 2][1] == "function"):
        return True
    return bool(re.fullmatch(r"[$\w]+", previous))


def brace_functions(text):
    tokens = _js_tokens(text)
    parens = {}
    opened_parens = []
    braces = []
    found = []
    for index, (kind, value, position) in enumerate(tokens):
        if kind == "string":
            continue
        if value == "(":
            opened_parens.append(index)
        elif value == ")" and opened_parens:
            parens[index] = opened_parens.pop()
        elif value == "{":
            function = _function_open(tokens, index, parens)
            start = position
            if function:
                boundary = next((j for j in range(index - 1, -1, -1)
                                 if tokens[j][1] in (";", "{", "}")), -1)
                start = tokens[boundary + 1][2]
            braces.append((function, start))
        elif value == "}" and braces:
            function, start = braces.pop()
            if function:
                found.append((_line(text, start), _line(text, position)))
    return found


def python_functions(text):
    tree = ast.parse(text)
    return [(min([node.lineno] + [d.lineno for d in node.decorator_list]), node.end_lineno)
            for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def js_imports(text):
    tokens = _js_tokens(text)
    for index, (kind, value, position) in enumerate(tokens):
        if kind != "string" or value.startswith("`"):
            continue
        previous = [token[1] for token in tokens[max(0, index - 2):index]]
        if previous[-1:] in (["from"], ["import"]) or previous in (["require", "("], ["import", "("]):
            specifier = re.sub(r"\\(['\"\\])", r"\1", value[1:-1])
            yield specifier, _line(text, position)


def _existing_module(root, candidate):
    path = root / candidate
    return path.is_dir() or path.is_file() or path.with_suffix(".py").is_file()


def python_imports(root, name, text):
    parent = PurePosixPath(name).parent
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
            level = 0
        elif isinstance(node, ast.ImportFrom):
            modules = [".".join(filter(None, (node.module, alias.name))) for alias in node.names
                       if alias.name != "*"] + ([node.module] if node.module else [])
            level = node.level
        else:
            continue
        bases = [parent]
        if level:
            for _ in range(level - 1):
                bases = [base.parent for base in bases]
        else:
            bases = [PurePosixPath("."), PurePosixPath("src"), parent]
        for module in modules:
            candidates = [base.joinpath(*module.split(".")) for base in bases]
            target = next((item for item in candidates if _existing_module(root, item)), None)
            if target is not None:
                yield target.as_posix(), node.lineno
                if isinstance(node, ast.ImportFrom):
                    break


def _layer_for(name, layers):
    matches = [layer for layer in layers if name == layer["path"].rstrip("/")
               or name.startswith(layer["path"].rstrip("/") + "/")]
    return max(matches, key=lambda item: len(item["path"]), default=None)


def _js_target(name, specifier):
    if not specifier.startswith("."):
        return None
    parts = list(PurePosixPath(name).parent.parts)
    for part in specifier.split("/"):
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part and part != ".":
            parts.append(part)
    return "/".join(parts)


def check_layers(root, name, text, layers):
    source = _layer_for(name, layers)
    if source is None:
        return []
    suffix = Path(name).suffix.lower()
    if suffix in JAVASCRIPT:
        imports = [(_js_target(name, value), line) for value, line in js_imports(text)]
    elif suffix in (".py", ".pyi"):
        imports = list(python_imports(root, name, text))
    else:
        return []
    violations = []
    for target, line in imports:
        destination = _layer_for(target, layers) if target else None
        if destination is None or destination is source:
            continue
        target_name = destination.get("name", destination["path"])
        if target_name in source["allow"] or any(
                target == item or target.startswith(item.rstrip("/") + "/") for item in source["allow"]):
            continue
        violations.append({"rule": "layer-import", "file": name, "line": line,
                           "sourceLayer": source.get("name", source["path"]), "targetLayer": target_name,
                           "target": target})
    return violations


def _check_file(root, name, text, config):
    violations = []
    line_count = len(text.splitlines())
    if line_count > config["maxFileLines"]:
        violations.append({"rule": "file-lines", "file": name, "lines": line_count,
                           "limit": config["maxFileLines"]})
    for item in config["bannedPatterns"]:
        for match in compile_pattern(item).finditer(text):
            violations.append({"rule": "banned-pattern", "file": name, "line": _line(text, match.start()),
                               "description": item["description"]})
    suffix = Path(name).suffix.lower()
    functions = []
    try:
        if suffix in (".py", ".pyi"):
            functions = python_functions(text)
        elif suffix in JAVASCRIPT or suffix in (".java", ".kt", ".cs"):
            functions = brace_functions(text)
        violations.extend(check_layers(root, name, text, config["layers"]))
    except SyntaxError as error:
        violations.append({"rule": "python-syntax", "file": name, "line": error.lineno, "message": error.msg})
    for start, end in functions:
        length = end - start + 1
        if length > config["maxFunctionLines"]:
            violations.append({"rule": "function-lines", "file": name, "line": start,
                               "lines": length, "limit": config["maxFunctionLines"]})
    return violations


def check_structure(root, files, config):
    violations = []
    limitations = []
    for name, text in files.items():
        violations.extend(_check_file(root, name, text, config))
        suffix = Path(name).suffix.lower()
        if suffix in JAVASCRIPT:
            limitations.append("JS/TS function/import checks use lexical analysis; computed imports, aliases, "
                               "template interpolation and complex syntax require the configured type/test tools.")
        elif suffix in CODE_EXTENSIONS and suffix not in (".py", ".pyi"):
            limitations.append("{}: function and dependency analysis is {}.".format(
                suffix, "limited to a brace-function heuristic; imports unsupported"
                if suffix in (".java", ".kt", ".cs") else "unsupported; file/pattern checks still apply"))
    return violations, sorted(set(limitations))
