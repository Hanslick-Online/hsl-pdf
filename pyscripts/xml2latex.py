#!/usr/bin/env python
from acdh_tei_pyutils.tei import ET
import os
import sys
import re
ns = {'tei': 'http://www.tei-c.org/ns/1.0', 'xml': "http://www.w3.org/XML/1998/namespace"}


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def node_text(node) -> str:
    return norm_ws("".join(node.itertext()))


def lines_on_lb(element) -> list[str]:
    lines: list[str] = []
    current: list[str] = []

    for node in element.iter():
        tag = node.tag.split("}")[-1]

        if node is element:
            if node.text and node.text.strip():
                current.append(node.text)
            continue

        if tag == "lb":
            line = norm_ws("".join(current)).rstrip(".")
            if line:
                lines.append(clean_text(line))
            current = []
            if node.tail and node.tail.strip():
                current.append(node.tail)
            continue

        if node.text and node.text.strip():
            current.append(node.text)
        if node.tail and node.tail.strip():
            current.append(node.tail)

    line = norm_ws("".join(current)).rstrip(".")
    if line:
        lines.append(clean_text(line))
    return lines

biblinfo = {'t': ['Eduard Hanslick, \\emph{Vom Musikalisch-Schönen: Ein Beitrag zur Revision der Ästhetik der Tonkunst}',
                  'Alexander Wilfing', 'Daniel Elsner und Meike Wilfing-Albrecht', '2023'],
            'c': ['\\emph{Eduard Hanslicks Schriften für die „Neue Freie Presse“}',
                  'Alexander Wilfing',
                  'Katharina Bamer, Daniel Elsner, Anna-Maria Pfiel und Fernando Sanz-Lázaro', '2023–2026'],
            'v': ['\\emph{Die Rezensionen zu Eduard Hanslicks „Vom Musikalisch-Schönen“ (1854–1857)}',
                  'Alexander Wilfing und Anna-Maria Pfiel', 'Daniel Elsner und Fernando Sanz-Lázaro', '2024–2025'],
            'd': ['\\emph{Dokumente zu Eduard Hanslicks „Vom Musikalisch-Schönen}',
                  'Alexander Wilfing und Meike Wilfing-Albrecht', 'Fernando Sanz-Lázaro',  '2025']
            }


def make_bibl(title, hsrg, mitarbeiter, year):
    return f"{title}, hrsg. von {hsrg} unter Mitarbeit von {mitarbeiter} (Wien: ACDH. {year})."


def fix_invalid_xml_id(xml_text):
    """ Fix invalid xml:id values that don't start with a letter or underscore """
    return re.sub(r'xml:id="([^a-zA-Z_])', r'xml:id="_\1', xml_text)


def make_name_list(names):
    names = [
        " ".join([n.strip() for n in name.split(",")][::-1])
        for name in list(dict.fromkeys(names))
    ]
    if len(names) > 1:
        names = ", ".join(names[:-1]) + " und " + names[-1]
    elif names:
        names = names[0]
    else:
        names = ""
    return names


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = text.replace("„ ", "„").replace(" “", "“").replace(" ,", ",").replace(" ’", "’")
    # fix common OCR/source spacing artifacts
    text = re.sub(r"\(\s+", "(", text)   # no space after '('
    text = re.sub(r"\s+\)", ")", text)   # no space before ')'
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)  # no space before punctuation
    return text


def escape_latex(text: str) -> str:
    # Escape literal characters that would break LaTeX when they come from TEI text.
    # (Do NOT run this on strings that already contain LaTeX commands/macros.)
    for ch in ("{", "}", "_", "&", "%", "#", "$"):
        text = text.replace(ch, rf"\{ch}")
    return text


def clean_text(text: str) -> str:
    return escape_latex(normalize_text(text))


def _is_emph_node(node) -> bool:
    """Return True if *node* itself introduces italic formatting."""
    tag = node.tag.split("}")[-1]
    return tag == "emph" or (tag == "hi" and node.attrib.get("rendition") == "#em")


def _has_emph_ancestor(node, root) -> bool:
    """Return True if any ancestor of *node* (up to but not including *root*) is <emph>."""
    parent = node.getparent()
    while parent is not None and parent is not root:
        if _is_emph_node(parent):
            return True
        parent = parent.getparent()
    return False


def _extract_note_text(note_element) -> str:
    """Recursively extract the text content of a <note> element for use in \\footnote{}.

    Uses a proper tree-walk so that formatting context (e.g. <emph>) is
    correctly propagated to descendant nodes like <rs>.
    """
    def _walk(node, in_emph: bool) -> list[str]:
        tag = node.tag.split("}")[-1]
        is_emph = _is_emph_node(node)
        cur_emph = in_emph or is_emph  # True inside this node and its children

        parts: list[str] = []

        # 1. Node's own .text (before any child elements)
        if node.text and node.text.strip():
            raw = escape_latex(node.text.strip())
            if cur_emph:
                raw = "\\textit{" + raw + "}"
            parts.append(raw)

        # 2. Process child elements (in document order)
        for child in node:
            parts.extend(_walk(child, cur_emph))

        # 3. Node's .tail (text after </node>, belongs to the *parent's* context)
        if node.tail and node.tail.strip():
            tail = escape_latex(re.sub(r"\s+", " ", node.tail))
            if tail != " ":
                if in_emph:  # parent's emph context, not this node's
                    tail = "\\textit{" + tail + "}"
                parts.append(tail)

        return parts

    # Walk the note's children (note_element itself is the root, not formatted)
    parts: list[str] = []
    if note_element.text and note_element.text.strip():
        parts.append(escape_latex(note_element.text.strip()))
    for child in note_element:
        parts.extend(_walk(child, in_emph=False))
    return normalize_text(" ".join(parts))


def _is_descendant_of_note(node, element) -> bool:
    """Check whether *node* is inside a <note> that is a descendant of *element*."""
    parent = node.getparent()
    while parent is not None and parent is not element:
        if parent.tag.split("}")[-1] == "note":
            return True
        parent = parent.getparent()
    return False


def process_paragraph(element):
    """
    Processes a paragraph element to combine all text, adding spaces where needed,
    and handle <lb>, <cb>, <note>, and inline elements properly.
    """
    result: list[str] = []
    skip_space = False
    for node in element.iter():
        tag = node.tag.split("}")[-1]  # remove namespace if present

        # Skip nodes that are descendants of a <note> (handled when <note> is encountered)
        if node is not element and _is_descendant_of_note(node, element):
            continue

        # Handle <note place="foot"> → \footnote{...}
        if tag == "note" and node.attrib.get("place") in {"foot", "bottom"}:
            fn_text = _extract_note_text(node)
            if fn_text:
                if result:
                    result[-1] += "\\footnote{" + fn_text + "}"
                else:
                    result.append("\\footnote{" + fn_text + "}")
            # Process the note's tail (text after the closing </note>)
            if node.tail and node.tail.strip():
                tail = escape_latex(re.sub(r"\s+", " ", node.tail))
                if tail != " ":
                    result.append(tail)
            continue

        text = ""
        tail = ""

        # Handle line or column breaks
        if tag in {"lb", "cb", "pb"}:
            if node.attrib.get("break") == "no":
                skip_space = True
        text = ""
        # Add the current node's text content
        if node.text:
            raw_text = node.text.strip() if node.text else ""
            raw_text = escape_latex(raw_text)
            want_emph = _is_emph_node(node) or (node is not element and _has_emph_ancestor(node, element))
            if want_emph:
                text = "\\textit{" + raw_text + "}"
            else:
                text = raw_text
        if node.tail and node.tail.strip():
            tail = escape_latex(re.sub(r"\s+", " ", node.tail))
            if tail == " ":
                tail = ""
            elif _has_emph_ancestor(node, element):
                tail = "\\textit{" + tail + "}"
        if skip_space and result:
            result[-1] += text + tail
            skip_space = False
        else:
            result.append(text + tail)
    spacing = "" if element.attrib.get("prev") == "true" else "\n\n"
    # At this point `result` may contain LaTeX macros (e.g. \textit{...}),
    # so only normalize whitespace/punctuation; escaping already happened per-text-segment.
    return spacing + normalize_text(" ".join(result))


def get_date(tree):
    date = tree.xpath(".//tei:monogr/tei:imprint/tei:date/@when", namespaces=ns)
    if date:
        date = date[0].split("-")
        for i in range(0, 3 - len(date)):
            date += [0]
    return date


def get_info(tree):
    def _titles_for(levels: list[str]) -> list[str]:
        out: list[str] = []
        for level in levels:
            for t in tree.xpath(f".//tei:titleStmt/tei:title[@level='{level}']", namespaces=ns):
                txt = clean_text(node_text(t))
                if txt:
                    out.append(txt)
        return out

    titles = _titles_for(["a"])
    if titles:
        titles += _titles_for(["s", "j"])
    else:
        titles = _titles_for(["s", "j"])
    if not titles:
        fallback_nodes = tree.xpath(".//tei:analytic/tei:title | .//tei:monogr/tei:title", namespaces=ns)
        titles = [clean_text(node_text(t)) for t in fallback_nodes if clean_text(node_text(t))]
    if tree.xpath(".//tei:titleStmt/tei:authors", namespaces=ns):
        authorsb = tree.xpath(".//tei:titleStmt/tei:authors/text()", namespaces=ns)
    else:
        authorsb = tree.xpath(".//tei:author", namespaces=ns)

    authors = []
    for elem in authorsb:
        if elem.text and elem.text.strip() and elem.text not in authors:
            authors.append(elem.text.strip())
    origdate = get_date(tree)
    origeditors = [
        elem.text
        for elem in tree.xpath(".//tei:monogr/tei:respStmt/tei:name", namespaces=ns)
        if elem.text
    ]
    return titles, make_name_list(authors), origdate, make_name_list(origeditors)


def get_source_desc_article_info(tree):
    """Extract structured bibliographic info from sourceDesc/biblStruct
    for building article title pages."""
    bs = tree.xpath(".//tei:sourceDesc//tei:biblStruct", namespaces=ns)
    if not bs:
        return None
    bs = bs[0]
    analytic_titles = [
        node_text(t)
        for t in bs.xpath("./tei:analytic/tei:title", namespaces=ns)
        if node_text(t)
    ]
    analytic_authors = [
        node_text(a)
        for a in bs.xpath("./tei:analytic/tei:author", namespaces=ns)
        if node_text(a)
    ]
    monogr_main = " ".join(
        [node_text(t) for t in bs.xpath("./tei:monogr/tei:title[@type='main']", namespaces=ns) if node_text(t)]
    ).strip()
    monogr_sub = " ".join(
        [node_text(t) for t in bs.xpath("./tei:monogr/tei:title[@type='sub']", namespaces=ns) if node_text(t)]
    ).strip()
    resp_text = " ".join(
        [node_text(r) for r in bs.xpath("./tei:monogr/tei:respStmt/tei:resp", namespaces=ns) if node_text(r)]
    ).strip()
    editor_names = [
        node_text(n)
        for n in bs.xpath("./tei:monogr/tei:respStmt/tei:name", namespaces=ns)
        if node_text(n)
    ]
    date_when = (bs.xpath("./tei:monogr/tei:imprint/tei:date/@when", namespaces=ns) or [""])[0]
    date_text = " ".join(
        [node_text(d) for d in bs.xpath("./tei:monogr/tei:imprint/tei:date", namespaces=ns) if node_text(d)]
    ).strip()
    return {
        'analytic_titles': analytic_titles,
        'analytic_authors': analytic_authors,
        'monogr_main': monogr_main,
        'monogr_sub': monogr_sub,
        'resp_text': resp_text,
        'editor_names': editor_names,
        'date_when': date_when,
        'date_text': date_text,
    }


def make_body(tree, document_type):
    text = ""
    chapters = tree.xpath(".//tei:text//tei:body//tei:div", namespaces=ns)
    for chapter in chapters:
        head = chapter.xpath("./tei:head", namespaces=ns)
        if head:
            head = process_paragraph(head[0]).strip()
            plain_head = strip_latex_commands(head)
            if len(plain_head) > 80:
                short = plain_head[:80]
            else:
                short = ""
            text += section(document_type, head, short) + "\n"

        paragraphs = chapter.xpath("./tei:p", namespaces=ns)
        for p in paragraphs:
            paragraph_text = process_paragraph(p)
            if paragraph_text:
                text += paragraph_text
    return text


def make_front(front):

    title_nodes = front.xpath(".//tei:titlePage//tei:docTitle/tei:titlePart[@type='main']", namespaces=ns)
    title = clean_text(norm_ws(" ".join("".join(n.itertext()) for n in title_nodes)))

    subtitle_nodes = front.xpath(".//tei:titlePage//tei:docTitle/tei:titlePart[@type='sub']", namespaces=ns)
    subtitles = [
        clean_text(norm_ws("".join(n.itertext())))
        for n in subtitle_nodes
        if norm_ws("".join(n.itertext()))
    ]

    bylines: list[str] = []
    for byline in front.xpath(".//tei:titlePage//tei:byline", namespaces=ns):
        bylines.extend(lines_on_lb(byline))

    imprints: list[str] = []
    for imprint in front.xpath(".//tei:titlePage//tei:docImprint", namespaces=ns):
        imprints.extend(lines_on_lb(imprint))
    

    edition_nodes = front.xpath(".//tei:titlePage//tei:docEdition", namespaces=ns)
    edition = clean_text(norm_ws(" ".join("".join(n.itertext()) for n in edition_nodes)))

    tei_root = front.getroottree().getroot()
    tei_xml_id = tei_root.attrib.get(f"{{{ns['xml']}}}id", "")
    i = tei_xml_id[:1].lower()
    if i not in biblinfo:
        raise ValueError(
            f"Unexpected TEI xml:id '{tei_xml_id}'. "
            f"Expected first character to be one of {sorted(biblinfo.keys())}."
        )

    bibl = make_bibl(*biblinfo[i])
    text = f"""\\frontmatter
        \\thispagestyle{{empty}}\\noindent {{\\linespread{{1}}\\selectfont {bibl}}}\\vspace{{.2\\textheight}}
        \\begin{{center}}
        {{\\Huge\\textbf{{{title.strip('.')}}}}}\\vspace{{.05\\textheight}}

        """
    if subtitles:
        text += "{\\LARGE\\textbf{" + ' '.join(subtitles).strip('.') + "}}\\vspace{.1\\textheight}\n\n"
    if bylines:
        text += "{\\large " + "\\\\\n".join([b.rstrip('.') for b in bylines]) + "}\n\\vfill\n\n"
    if edition:
        text += "{\\small " + edition.strip('.') + "}\n\\vfill\n\n"
    if imprints:
        text += "\\\\\n".join([i.rstrip('.') for i in imprints])
    return text + "\\end{center}\\clearpage\n\\mainmatter\n"


def strip_latex_commands(text: str) -> str:
    """Remove LaTeX commands from text, keeping only the plain content."""
    text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"[{}]", "", text)
    return text.strip()


def protect_latex_commands(text: str) -> str:
    """Add \\protect before fragile LaTeX commands so they survive moving arguments (headers, TOC)."""
    for cmd in ("textit", "textbf", "emph", "textsc", "textsf", "texttt"):
        text = text.replace(f"\\{cmd}{{", f"\\protect\\{cmd}{{")
    return text


def section(document, text, shorttext=""):
    if shorttext:
        shorttext = strip_latex_commands(shorttext)
        shorttext = f"[{shorttext}]"
    # Protect fragile commands in the full title for page headers (titlesec \chaptertitle)
    protected = protect_latex_commands(text)
    if document == "book":
        section = "chapter"
    else:
        section = "section"
    return f"\n\n\\{section}{shorttext}" + "{" + protected + "}"


def transform_tei_to_latex(input_file, output_file):
    # Parse the XML-TEI file
    with open(input_file, "r", encoding="utf-8") as f:
        xml_text = f.read()
    fixed_xml_text = fix_invalid_xml_id(xml_text)

    tree = ET.fromstring(fixed_xml_text.encode("utf-8"))
    # tree = TeiReader(input_file)

    tei_xml_id = tree.attrib.get(f"{{{ns['xml']}}}id", "")
    if not tei_xml_id:
        tei_xml_id = os.path.basename(input_file)
    prefix = tei_xml_id[:1].lower() if tei_xml_id else ""
    bibl = make_bibl(*biblinfo[prefix]) if prefix in biblinfo else ""

    Titles, Author, Date, Editors = get_info(tree)
    front = tree.xpath(".//tei:text//tei:front", namespaces=ns)
    has_title_page = bool(tree.xpath(".//tei:text//tei:front//tei:titlePage", namespaces=ns))
    document_type = "book" if has_title_page else "article"

    # Example: Extracting some TEI elements and converting to LaTeX
    Title = ""
    if Titles:
        Titles = [clean_text(i) for i in Titles if len(clean_text(i)) > 0]
        Title = Titles[0]
        if Titles[1:]:
            Subtitle = "\\\\".join([f"\\Large{{{title}}}" for title in Titles[1:] if title.strip()])
            Title = "\\\\".join([Title, Subtitle])
        if Editors:
            Title = "\\\\".join([Title, f"\\large{{Herausgegeben von {Editors}}}"])

    # Systematize maketitle fields for articles:
    # title <- source line (journal info) + item line (author, article title)
    # author <- empty (author is embedded in item line)
    # date <- empty (date is in source line or item line)
    if document_type == "article":
        src_info = get_source_desc_article_info(tree)

        # Check if titleStmt has explicit article title (level='a' with type='main')
        a_main_nodes = tree.xpath(
            ".//tei:titleStmt/tei:title[@level='a'][@type='main']", namespaces=ns
        )
        has_explicit_article_title = bool(a_main_nodes)

        # --- Build source line (journal/publication info) ---
        source_line = ""
        if src_info and src_info['editor_names']:
            parts = []
            if src_info['monogr_main']:
                main = clean_text(src_info['monogr_main'])
                if "„" not in main and "\u201E" not in main:
                    main = "\\emph{" + main + "}"
                parts.append(main)
            editors_str = clean_text(make_name_list(src_info['editor_names']))
            resp = clean_text(src_info['resp_text']) if src_info['resp_text'] else "Herausgegeben von"
            parts.append(f"{resp} {editors_str}")
            if src_info['monogr_sub']:
                parts.append(clean_text(src_info['monogr_sub']))
            # When analytic/title is issue info (no type='main' on level='a'),
            # append it to the source line rather than treating it as the article title.
            if not has_explicit_article_title and src_info['analytic_titles']:
                parts.append(clean_text(src_info['analytic_titles'][0]))
            source_line = ". ".join(p.rstrip('.') for p in parts if p) + "."

        # --- Build article title ---
        if has_explicit_article_title:
            article_parts = []
            for t in a_main_nodes:
                txt = clean_text(node_text(t))
                if txt:
                    article_parts.append(txt)
            a_sub_nodes = tree.xpath(
                ".//tei:titleStmt/tei:title[@level='a'][@type='sub']", namespaces=ns
            )
            for t in a_sub_nodes:
                txt = clean_text(node_text(t))
                if txt:
                    article_parts.append(txt)
            article_title = ". ".join(p.rstrip('.') for p in article_parts if p)
        else:
            # Fallback: get article title from body head elements (e.g. c__ documents)
            heads = tree.xpath(
                ".//tei:text//tei:body//tei:div[1]/tei:head", namespaces=ns
            )
            article_parts = [
                clean_text(node_text(h))
                for h in heads if clean_text(node_text(h))
            ]
            article_title = " ".join(article_parts) if article_parts else ""

        # --- Build item line (Author, Title) ---
        if src_info and src_info['analytic_authors']:
            sd_author = clean_text(make_name_list(src_info['analytic_authors']))
        else:
            sd_author = Author

        item_parts = []
        if sd_author:
            item_parts.append(sd_author)
        if article_title:
            item_parts.append(article_title.rstrip('.'))

        # For non-journal documents (no source line), append the year
        if not source_line and src_info:
            dw = src_info['date_when'] or src_info['date_text']
            if dw:
                year = clean_text(dw.split('-')[0] if '-' in dw else dw)
                item_parts.append(year)

        item_line = ", ".join(item_parts) + "."

        # --- Assemble Title; clear Author and Date ---
        title_lines: list[str] = []
        if source_line:
            title_lines.append(f"{{\\large {source_line}}}")
        title_lines.append(f"{{\\Large {item_line}}}")
        Title = "\\\\[1em]".join(title_lines)
        Author = ""
        Date = ""
    latex_content = []
    latex_content.append(f"\\documentclass[a4paper]{{{document_type}}}")
    latex_content.append("\\usepackage{polyglossia}")
    latex_content.append("\\setmainlanguage[variant=austrian]{german}")
    latex_content.append("\\usepackage{tracklang}")
    # latex_content.append("\\usepackage[austrian]{babel}")
    latex_content.append("\\usepackage{fontspec,xltxtra,xunicode}")
    latex_content.append("\\usepackage{microtype}")
    latex_content.append("\\usepackage{geometry}")
    latex_content.append("\\usepackage{emptypage}")
    latex_content.append("\\usepackage[pagestyles]{titlesec}")
    latex_content.append("\\titleformat{\\chapter}[display]{\\normalfont\\bfseries}{}{0pt}{\\Large}")
    latex_content.append("\\usepackage[de-AT]{datetime2}")
    latex_content.append("\\geometry{left=35mm, right=35mm, top=35mm, bottom=35mm}")
    latex_content.append("\\setmainfont{Noto Serif}")
    latex_content.append("\\widowpenalty=10000")
    latex_content.append("\\clubpenalty=10000")
    latex_content.append(
        "\\newpagestyle{mystyle}{\\sethead[\\thepage][][\\chaptertitle]{\\chaptertitle}{}{\\thepage}}\\pagestyle{mystyle}")
    latex_content.append(f"\\title{{{Title}}}")
    latex_content.append(f"\\author{{{Author}}}")
    if document_type != "article":
        if Date[1] == 0:
            Date = Date[0]
        else:
            Date = f"\\DTMdisplaydate{{{Date[0]}}}{{{Date[1]}}}{{{Date[2]}}}" + "{gregorian}"
    latex_content.append(f"\\date{{{Date}}}")
    latex_content.append("\\begin{document}")
    if document_type == "book" and front:
        latex_content.append(make_front(front[0]))
    else:
        if document_type == "article" and bibl:
            latex_content.append(
                "\\begingroup\\linespread{1}\\selectfont\\small\\noindent "
                + bibl
                + "\\par\\endgroup"
            )
            latex_content.append("\\vspace{0.5\\baselineskip}")
            latex_content.append("\\begingroup\\let\\newpage\\relax\\let\\clearpage\\relax\\let\\cleardoublepage\\relax")
            latex_content.append("\\maketitle")
            latex_content.append("\\endgroup")
        else:
            latex_content.append("\\maketitle")
    latex_content.append(make_body(tree, document_type))

    latex_content.append("\\end{document}")

    # Write the LaTeX content to the output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(latex_content))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python transform_tei_to_latex.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    transform_tei_to_latex(input_file, output_file)
