#!/usr/bin/env python3
# coding: utf-8

import re
from pathlib import Path
import sys
import csv

CONFIG_FILE = 'rules.tsv'
LANG_FILES = {
    'zh': {'md': 'README.zh.md', 'html_in': 'index.zh.html', 'html_out': 'index.zh.html'},
    'en': {'md': 'README.md',   'html_in': 'index.html',   'html_out': 'index.html'},
}

def load_rules(config_file: str, lang: str):
    rules = []
    with open(config_file, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row.get('lang') != lang:
                continue
            heading = row.get('heading_regex')
            parser_name = row.get('parser')
            slot_id = row.get('slot_id')
            if not heading or not parser_name or not slot_id:
                continue
            pattern = re.compile(heading, re.MULTILINE)
            parser = globals().get(parser_name)
            if not callable(parser):
                continue
            rules.append(MenuRule(pattern, parser, slot_id))
    return rules

# Colored logging
def log_info(msg):
    print(f"\033[32m[INFO]\033[0m {msg}")
def log_debug(msg):
    print(f"\033[36m[DEBUG]\033[0m {msg}")
def log_error(msg):
    print(f"\033[31m[ERROR]\033[0m {msg}")

from typing import List, Dict, Pattern, Callable, Any
from dataclasses import dataclass

@dataclass
class MenuRule:
    heading_regex: Pattern      # regex to match the Markdown heading line
    parser: Callable[[str], Any]  # function to parse that section
    slot_id: str                  # HTML slot identifier (data-menu or comment marker)

def parse_simple_items(section: str) -> List[Dict[str, str]]:
    """
    Parse lines like:
      - [LLVM Tutorial](https://llvm.org/docs/tutorial/) – LLVM Tutorial
    Returns a list of dicts with keys: title, href, desc.
    """
    pattern = re.compile(r'- \[([^]]+)\]\(([^)]+)\)\s*[–-]\s*(.+)')
    items = []
    for line in section.splitlines():
        m = pattern.match(line.strip())
        if m:
            items.append({
                "title": m.group(1).strip(),
                "href": m.group(2).strip(),
                "desc":  m.group(3).strip()
            })
    return items

def parse_repo_items(section: str) -> List[Dict[str, str]]:
    """
    Parse lines like:
      - [LLVM](https://github.com/llvm/llvm-project) <!--![llvm](https://...)-->
    Returns list of dicts with keys: name, href, img (optional).
    """
    pattern = re.compile(
        r'- \[([^]]+)\]\(([^)]+)\)'
        r'(?:\s*<!--!\[[^\]]*\]\(([^)]+)\)-->)?'
    )
    items = []
    for line in section.splitlines():
        m = pattern.match(line.strip())
        if m:
            items.append({
                "name": m.group(1).strip(),
                "href": m.group(2).strip(),
                "img":  m.group(3).strip() if m.group(3) else ""
            })
    return items

def parse_conference_items(section: str) -> List[Dict[str, str]]:
    """
    Parse lines like:
      - [CGO](https://.../cgo) `CORE A` `CCF B`
    Returns list of dicts with keys: name, href, tags (list).
    """
    item_pattern = re.compile(r'- \[([^]]+)\]\(([^)]+)\)')
    tag_pattern  = re.compile(r'`([^`]+)`')
    items = []
    for line in section.splitlines():
        li = line.strip()
        m = item_pattern.match(li)
        if m:
            tags = tag_pattern.findall(li[m.end():])
            items.append({
                "name": m.group(1).strip(),
                "href": m.group(2).strip(),
                "tags": tags
            })
    return items

def parse_glossary_items(section: str) -> List[Dict[str, str]]:
    """
    Parse lines like:
      - [AOT](https://en.wikipedia.org/wiki/Ahead-of-time_compilation)
    Returns a list of dicts with keys: name, href.
    """
    pattern = re.compile(r'- \[([^]]+)\]\(([^)]+)\)')
    items = []
    for line in section.splitlines():
        m = pattern.match(line.strip())
        if m:
            items.append({
                "name": m.group(1).strip(),
                "href": m.group(2).strip()
            })
    return items

class Node:
    def __init__(self, level: int, text: str):
        self.level = level
        self.text  = text.strip()
        self.children = []
        self.id = ""

def parse_markdown(md: str):
    pat = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
    roots, stack = [], []
    for m in pat.finditer(md):
        level = len(m.group(1))
        node  = Node(level, m.group(2))
        while stack and stack[-1].level >= level:
            stack.pop()
        if not stack:
            roots.append(node)
        else:
            stack[-1].children.append(node)
        stack.append(node)
    return roots

def gen_ids(node_list):
    """Assign menuX / menuXsubY … IDs to all nodes"""
    for i, root in enumerate(node_list, 1):
        root.id = f"menu{i}"
        for j, sub in enumerate(root.children, 1):
            sub.id = f"{root.id}sub{j}"
            for k, sub2 in enumerate(sub.children, 1):
                sub2.id = f"{sub.id}sub{k}"

def render_html(nodes):
    html = []
    for n in nodes:
        if not n.children:
            html.append(f'<a class="list-group-item" href="#{n.id}">{n.text}</a>')
        else:
            html.append(
                f'<a class="list-group-item collapsed" data-toggle="collapse" '
                f'data-parent="#sidebar" aria-expanded="false" href="#{n.id}">'
                f'{n.text}</a>')
            html.append(f'<div class="collapse" id="{n.id}">')
            html.extend(render_html(n.children))
            html.append('</div>')
    return html

def revert_injects(html_src: str) -> str:
    """
    Remove only the content between <!-- inject-xxx --> and <!-- inject-xxx-end --> markers,
    preserving the markers themselves.
    """
    pattern = re.compile(
        r'([ \t]*<!--\s*inject-[\w-]+\s*-->)[\s\S]*?([ \t]*<!--\s*inject-[\w-]+?-end\s*-->)',
        re.DOTALL)
    return pattern.sub(r'\1\n\2', html_src)

def inject_slot(html_src: str, slot_id: str, fragment: str) -> str:
    """
    Replace the HTML slot identified by slot_id with fragment.
    Supports:
      - <ul data-menu="slot_id"> ... </ul>
      - <!-- inject-slot_id --> ... <!-- inject-slot_id-end -->
    """
    # Try comment markers first
    comment_pattern = re.compile(
        rf'<!--\s*inject-{re.escape(slot_id)}\s*-->.*?<!--\s*inject-{re.escape(slot_id)}-end\s*-->',
        re.DOTALL)
    comment_replacement = f'<!-- inject-{slot_id} -->\n{fragment}\n<!-- inject-{slot_id}-end -->'
    html_src, n = comment_pattern.subn(comment_replacement, html_src)
    if n > 0:
        return html_src
    # Try <ul data-menu="slot_id"> ... </ul>
    ul_pattern = re.compile(
        rf'(<ul[^>]*data-menu\s*=\s*["\']{re.escape(slot_id)}["\'][^>]*>)(.*?)(</ul>)',
        re.DOTALL)
    def ul_repl(m):
        return f"{m.group(1)}\n{fragment}\n{m.group(3)}"
    html_src, n = ul_pattern.subn(ul_repl, html_src)
    if n > 0:
        return html_src
    # If neither found, just return unchanged (or raise if strict)
    # raise RuntimeError(f"Cannot find slot {slot_id} in template.")
    return html_src

def extract_section(md_text: str, heading_regex: Pattern) -> str:
    """
    Given the full Markdown text and a heading regex, extract the section
    from the heading line until the next heading of same or higher level.
    """
    matches = list(heading_regex.finditer(md_text))
    if not matches:
        return ""
    m = matches[0]
    start = m.start()
    # Determine heading level by number of #s
    heading_line = m.group(0)
    level = len(re.match(r'^(#+)', heading_line).group(1))
    # Find the next heading of same or higher level
    next_heading = re.compile(rf'^#{{1,{level}}}\s+', re.MULTILINE)
    next_m = next_heading.search(md_text, pos=m.end())
    end = next_m.start() if next_m else len(md_text)
    return md_text[m.end():end].strip()

def render_link_ul(items):
    lines = []
    for item in items:
        lines.append(
            f'<li>'
            f'<a href="{item["href"]}">{item["name"]}</a>'
            f'</li>'
        )
    return "\n".join(lines) if lines else ""

def render_simple_ul(items):
    lines = []
    for item in items:
        lines.append(
            f'<li>'
            f'<span class="tagcloud mt-50 widget_tagcloud">'
            f'<a class="tag-cloud-link" href="{item["href"]}">{item["title"]}</a>'
            f'</span>{item["desc"]}'
            f'</li>'
        )
    return "<ul class=\"tagcloud-list\">\n" + "\n".join(lines) + "\n</ul>" if lines else ""

def render_repo_grid(items):
    html = []
    # wrap every 6 items in a .row
    for i in range(0, len(items), 6):
        chunk = items[i:i+6]
        html.append('<div class="row">')
        for item in chunk:
            html.append(
                '    <div class="col-md-2">'
                f'        <a class="block-github" href="{item["href"]}" target="_blank">'
                f'            <img src="{item["img"]}"/>'
                '        </a>'
                '        <div class="block-github-text">'
                f'            <p><mark><b>{item["name"]}</b></mark></p>'
                '        </div>'
                '    </div>'
            )
        html.append('</div>')
    return "\n".join(html) if html else ""

def render_confs_ul(items):
    lines = []
    for item in items:
        badges = "".join(
            f'<span class="badge badge-core">{tag}</span>'
            for tag in item.get("tags", [])
        )
        lines.append(
            f'<li>'
            f'<a href="{item["href"]}">{item["name"]}</a>'
            f'{badges}'
            f'</li>'
        )
    return "<ul class=\"conference-list\">\n" + "\n".join(lines) + "\n</ul>" if lines else ""

def choose_renderer(rule: MenuRule) -> Callable[[Any], str]:
    # Pick a renderer based on the parser function
    if rule.parser is parse_simple_items:
        return render_simple_ul
    if rule.parser is parse_repo_items:
        return render_repo_grid
    if rule.parser is parse_conference_items:
        return render_confs_ul
    if rule.parser is parse_glossary_items:
        return render_link_ul
    # fallback
    return lambda items: ""

def main():
    args = sys.argv[1:]
    log_info("Starting inject-new.py for all languages")
    do_revert = "--revert" in args

    if do_revert:
        for lang, files in LANG_FILES.items():
            html_src = Path(files['html_in']).read_text(encoding="utf-8")
            new_html = revert_injects(html_src)
            Path(files['html_out']).write_text(new_html, encoding="utf-8")
            log_info(f"Reverted injected blocks in {lang}")
        return

    for lang, files in LANG_FILES.items():
        log_info(f"Processing language: {lang}")
        rules = load_rules(CONFIG_FILE, lang)
        md_text = Path(files['md']).read_text(encoding="utf-8")
        html_src = Path(files['html_in']).read_text(encoding="utf-8")
        for rule in rules:
            if rule.parser is None:
                continue
            log_debug(f"Processing slot: {rule.slot_id} for {lang}")
            section_text = extract_section(md_text, rule.heading_regex)
            if not section_text:
                continue
            items = rule.parser(section_text)
            log_debug(f"Found {len(items)} items for slot {rule.slot_id} in {lang}")
            renderer = choose_renderer(rule)
            fragment = renderer(items)
            html_src = inject_slot(html_src, rule.slot_id, fragment)
        # build and inject TOC
        roots = parse_markdown(md_text)
        gen_ids(roots)
        toc_html = "\n".join(render_html(roots))
        html_src = inject_slot(html_src, "index", toc_html)
        Path(files['html_out']).write_text(html_src, encoding="utf-8")
        log_info(f"Injection complete for {lang}, output written to {files['html_out']}")

if __name__ == "__main__":
    main()