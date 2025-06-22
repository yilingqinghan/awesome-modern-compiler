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
    return sections

def parse_section_items(section_text):
    """
    从一个段落里，提取所有 '- [标题](链接) – 描述'，
    返回 [{'title':…, 'href':…, 'desc':…}, …]
    """
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\) – (.+)', line)
        if m:
            title, href, desc = m.groups()
            items.append({'title': title, 'href': href, 'desc': desc})
    return items

def parse_menu4_items(section_text: str) -> list:
    """
    从 menu4 Markdown 段落解析条目 '- [Name](url) – tag1, tag2, ...',
    返回 [{'name': name, 'href': url, 'tags': [tag1, tag2, ...]}, ...]
    """
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
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\)\s*`?!\[[^\]]*\]\(([^)]+)\)`?', line)
        if m:
            name, href, img = m.groups()
            items.append({'name': name, 'href': href, 'img': img})
    return items

def parse_menu13_items(section_text: str) -> list:
    """
    解析 menu13 Markdown 格式:
    - [标签名](链接)
    返回 [{'name': ..., 'href': ...}, ...]
    """
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\)', line)
        if m:
            name, href = m.groups()
            items.append({'name': name, 'href': href})
    return items

def parse_menu14_items(section_text: str) -> list:
    """
    解析 menu14 Markdown 格式:
    - [会议名](链接) :: CORE评级, CCF评级
    返回 [{'name': ..., 'href': ..., 'tags': [...]}, ...]
    """
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        m = re.match(r'- \[([^\]]+)\]\(([^)]+)\)\s*::\s*(.+)', line)
        if m:
            name, href, tag_str = m.groups()
            tags = [t.strip() for t in tag_str.split(',')]
            items.append({'name': name, 'href': href, 'tags': tags})
    return items

def inject_menu_generic(html: str, items: list, marker_id: int) -> str:
    """
    通用注入函数：将 items 注入到 <!-- inject-menu{marker_id} --> 标记后
    """
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
    """
    根据 parse_menu4_items 生成的 items 列表，把人物与标签两列 HTML
    注入到 <!-- inject-menu4 --> 标记后面。
    items: [{'name':..., 'href':..., 'tags':[...]}, ...]
    """
    # items 已经解析好，直接生成 HTML

    # 1. 左侧人物列
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

    # 2. 右侧标签组
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

    # 3. 注入到 <!-- inject-menu4 -->
    injection = '\n' + '\n'.join(left + right)
    return html.replace('<!-- inject-menu4 -->',
                        '<!-- inject-menu4 -->' + injection)

def inject_menu5(html: str, items: list) -> str:
    """
    注入 menu5 区块，每 6 个元素包在一个 <div class="row"> 里
    """
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
    """
    注入 menu13 区块，每项一个 <a class="tag-cloud-link"> 标签
    """
    links = ''.join(
        f'<a class="tag-cloud-link" href="{it["href"]}">{it["name"]}</a>'
        for it in items
    )
    injection = '\n' + links
    return html.replace('<!-- inject-menu13 -->', '<!-- inject-menu13 -->' + injection)

def inject_menu14(html: str, items: list) -> str:
    """
    注入 menu14 区块，每项一个 <li>，后跟多个 <span class="badge badge-core">标签</span>
    """
    lines = []
    for it in items:
        spans = ''.join(f'<span class="badge badge-core">{tag}</span>' for tag in it['tags'])
        lines.append(f'<li><a href="{it["href"]}">{it["name"]}</a>{spans}</li>')
    injection = '\n' + '\n'.join(lines)
    return html.replace('<!-- inject-menu14 -->', '<!-- inject-menu14 -->' + injection)

def inject_menu15(html: str, items: list) -> str:
    """
    注入 menu15 区块，每项一个 <li>，后跟多个 <span class="badge badge-core">标签</span>
    """
    lines = []
    for it in items:
        spans = ''.join(f'<span class="badge badge-core">{tag}</span>' for tag in it['tags'])
        lines.append(f'<li><a href="{it["href"]}">{it["name"]}</a>{spans}</li>')
    injection = '\n' + '\n'.join(lines)
    return html.replace('<!-- inject-menu15 -->', '<!-- inject-menu15 -->' + injection)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revert', action='store_true',
                        help='删除所有 inject-menuN 与 inject-menuN-end 之间的内容')
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
            menu10_items = parse_section_items(sections[9]) if len(sections) > 9 else []
            menu12_items = parse_section_items(sections[11]) if len(sections) > 11 else []
            menu14_items = parse_menu14_items(sections[13]) if len(sections) > 13 else []
            menu15_items = parse_menu14_items(sections[14]) if len(sections) > 14 else []
            menu4_items  = parse_menu4_items(sections[3]) if len(sections) > 3 else []
            menu5_items  = parse_menu5_items(sections[4]) if len(sections) > 4 else []
            menu13_items = parse_menu13_items(sections[12]) if len(sections) > 12 else []

            html = inject_menu_generic(html, menu2_items, 2)
            html = inject_menu_generic(html, menu3_items, 3)
            html = inject_menu4(html, menu4_items)
            html = inject_menu5(html, menu5_items)
            html = inject_menu_generic(html, menu6_items, 6)
            html = inject_menu_generic(html, menu7_items, 7)
            html = inject_menu_generic(html, menu8_items, 8)
            html = inject_menu13(html, menu13_items)
            html = inject_menu14(html, menu14_items)
            html = inject_menu15(html, menu15_items)
            html = inject_menu_generic(html, menu10_items, 10)
            html = inject_menu_generic(html, menu12_items, 12)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)


if __name__ == '__main__':
    main()