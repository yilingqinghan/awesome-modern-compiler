import re
import argparse

def revert_injects(html: str) -> str:
    """
    Remove everything between each
      <!-- inject-menuN -->  and  <!-- inject-menuN-end -->
    markers (for any N), leaving the markers themselves in place.
    """
    pattern = re.compile(
        r'<!--\s*inject-menu(?P<id>\d+)\s*-->.*?<!--\s*inject-menu(?P=id)-end\s*-->',
        flags=re.DOTALL
    )
    # Replace each match with just the start and end markers
    return pattern.sub(lambda m: f'<!-- inject-menu{m.group("id")} -->\n<!-- inject-menu{m.group("id")}-end -->', html)


def parse_md_sections(md_text):
    heads = [(m.start(), m.end(), len(m.group(1)))
             for m in re.finditer(r'^(##+)\s+.+', md_text, flags=re.MULTILINE)]
    sections = []
    for i, (_, end, _) in enumerate(heads):
        start = end
        finish = heads[i+1][0] if i+1 < len(heads) else len(md_text)
        sections.append(md_text[start:finish])
#     for i,j in enumerate(sections):
#         print(i,j)
    return sections

def parse_section_items(section_text):
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\) – (.+)', line)
        if m:
            title, href, desc = m.groups()
            items.append({'title': title, 'href': href, 'desc': desc})
    return items

def parse_menu4_items(section_text: str) -> list:
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\)\s*–\s*(.+)', line)
        if m:
            name, href, tags_str = m.groups()
            tags = [t.strip() for t in tags_str.split(',')]
            items.append({'name': name, 'href': href, 'tags': tags})
    return items

def parse_menu5_items(section_text: str) -> list:
    items = []
    pattern = re.compile(
        r'- \[([^\]]+)\]\(([^)]+)\)\s*<!--\s*!\[[^\]]*\]\(([^)]+)\)\s*-->'
    )
    for line in section_text.splitlines():
        line = line.strip()
        m = pattern.match(line)
        if m:
            name, href, img = m.groups()
            items.append({'name': name, 'href': href, 'img': img})
    return items

def parse_menu13_items(section_text: str) -> list:
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\)', line)
        if m:
            name, href = m.groups()
            items.append({'name': name, 'href': href})
    return items

def parse_menu14_items(section_text: str) -> list:
    items = []
    pattern = re.compile(
        r'- \[([^\]]+)\]\(([^)]+)\)\s*((?:`[^`]+`\s*)+)'
    )
    for line in section_text.splitlines():
        line = line.strip()
        m = pattern.match(line)
        if m:
            name, href, tags_part = m.groups()
            tags = re.findall(r'`([^`]+)`', tags_part)
            items.append({'name': name, 'href': href, 'tags': tags})
    return items

def inject_menu_generic(html: str, items: list, marker_id: int) -> str:
    marker = f'<!-- inject-menu{marker_id} -->'
    injection = ''.join(
        f'\n<li>'
          f'<span class="tagcloud mt-50 widget_tagcloud">'
            f'<a class="tag-cloud-link" href="{it["href"]}">{it["title"]}</a>'
          f'</span>'
          f'{it["desc"]}'
        f'</li>'
        for it in items
    )
    return html.replace(marker, marker + injection)

def inject_menu4(html: str, items: list) -> str:
    left = [
        '<div class="col-md-3">',
        '  <div class="entry-main-content">',
        '    <ul>',
    ]
    for it in items:
        left.append(f'      <li><a href="{it["href"]}">{it["name"]}</a></li>')
    left += [
        '    </ul>',
        '  </div>',
        '</div>',
    ]

    right = [
        '<div class="col-md-9">',
        '  <ul>',
    ]
    for it in items:
        links = ''.join(
            f'<a class="tag-cloud-link" href="">{tag}</a>'
            for tag in it['tags']
        )
        right += [
            '    <li>',
            f'      <span class="tagcloud mt-50 widget_tagcloud">{links}</span>',
            '    </li>',
        ]
    right += [
        '  </ul>',
        '</div>',
    ]

    injection = '\n' + '\n'.join(left + right)
    return html.replace('<!-- inject-menu4 -->',
                        '<!-- inject-menu4 -->' + injection)

def inject_menu5(html: str, items: list) -> str:
    blocks = []
    for i in range(0, len(items), 6):
        row = ['<div class="row">']
        for it in items[i:i+6]:
            block = f'''    <div class="col-md-2">
        <a class="block-github" href="{it['href']}" target="_blank">
            <img src="{it['img']}"/>
        </a>
        <div class="block-github-text">
            <p><mark><b>{it['name']}</b></mark></p>
        </div>
    </div>'''
            row.append(block)
        row.append('</div>')
        blocks.append('\n'.join(row))
    injection = '\n' + '\n'.join(blocks)
    return html.replace('<!-- inject-menu5 -->', '<!-- inject-menu5 -->' + injection)

def inject_menu13(html: str, items: list) -> str:
    links = ''.join(
        f'<a class="tag-cloud-link" href="{it["href"]}">{it["name"]}</a>'
        for it in items
    )
    injection = '\n' + links
    return html.replace('<!-- inject-menu13 -->', '<!-- inject-menu13 -->' + injection)

def inject_menu14(html: str, items: list) -> str:
    lines = []
    for it in items:
        spans = ''.join(f'<span class="badge badge-core">{tag}</span>' for tag in it['tags'])
        lines.append(f'<li><a href="{it["href"]}">{it["name"]}</a>{spans}</li>')
    injection = '\n' + '\n'.join(lines)
    return html.replace('<!-- inject-menu14 -->', '<!-- inject-menu14 -->' + injection)

def inject_menu15(html: str, items: list) -> str:
    lines = []
    for it in items:
        spans = ''.join(f'<span class="badge badge-core">{tag}</span>' for tag in it['tags'])
        lines.append(f'<li><a href="{it["href"]}">{it["name"]}</a>{spans}</li>')
    injection = '\n' + '\n'.join(lines)
    return html.replace('<!-- inject-menu15 -->', '<!-- inject-menu15 -->' + injection)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revert', action='store_true')
    args = parser.parse_args()

    targets = [
        ("README.md", "index.html"),
        ("README.zh.md", "index.zh.html"),
    ]

    for md_path, html_path in targets:
        md = open(md_path, encoding='utf-8').read()
        html = open(html_path, encoding='utf-8').read()

        if args.revert:
            html = revert_injects(html)
        else:
            sections = parse_md_sections(md)
            menu2_items  = parse_section_items(sections[1]) if len(sections) > 1 else []
            menu3_items  = parse_section_items(sections[2]) if len(sections) > 2 else []
            menu6_items  = parse_section_items(sections[5]) if len(sections) > 5 else []
            menu7_items  = parse_section_items(sections[6]) if len(sections) > 6 else []
            menu8_items  = parse_section_items(sections[7]) if len(sections) > 7 else []
            menu9_items = parse_section_items(sections[8]) if len(sections) > 8 else []
            menu12_items = parse_section_items(sections[11]) if len(sections) > 11 else []
            menu14_items = parse_menu14_items(sections[13]) if len(sections) > 13 else []
            menu15_items = parse_menu14_items(sections[14]) if len(sections) > 14 else []
            menu4_items  = parse_menu4_items(sections[3]) if len(sections) > 3 else []
            menu5_items  = parse_menu5_items(sections[4]) if len(sections) > 4 else []
            menu13_items = parse_menu13_items(sections[12]) if len(sections) > 12 else []

            html = inject_menu_generic(html, menu2_items, 2)
            html = inject_menu_generic(html, menu3_items, 3)
            html = inject_menu_generic(html, menu6_items, 6)
            html = inject_menu_generic(html, menu7_items, 7)
            html = inject_menu_generic(html, menu8_items, 8)
            html = inject_menu_generic(html, menu9_items, 9)
            html = inject_menu_generic(html, menu12_items, 12)
            html = inject_menu4(html, menu4_items)
            html = inject_menu5(html, menu5_items)
            html = inject_menu13(html, menu13_items)
            html = inject_menu14(html, menu14_items)
            html = inject_menu15(html, menu15_items)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)


if __name__ == '__main__':
    main()