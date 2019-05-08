from bs4 import BeautifulSoup


def h_tag_to_int(h_tag):
    return int(h_tag.strip("h"))


def render_tocs(html):
    APPLICABLE_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p"]

    soup = BeautifulSoup(html, "html.parser")
    tocs = []
    previous_h_level = 0

    # Build the Tabsles of Contents
    tag = soup.find(APPLICABLE_TAGS)  # Find the first applicable tag
    while tag is not None:
        # Handle p Tags
        if tag.name == "p":
            if "".join(str(tag.string).split()) == "#toc":
                tocs.append(
                    {
                        "p_tag": tag,
                        "max_h_level": previous_h_level,
                        "h_tags": [],
                        "ended": False,
                    }
                )

        # Handle h Tags
        else:
            for toc in tocs:
                if toc["ended"] is False:
                    if h_tag_to_int(tag.name) > toc["max_h_level"]:
                        toc["h_tags"].append(tag)
                    else:
                        toc["ended"] = True
            previous_h_level = h_tag_to_int(tag.name)

        tag = tag.find_next(APPLICABLE_TAGS)

    # Add the Tables of Contents
    for toc in tocs:
        toc["p_tag"].clear()
        ul = soup.new_tag("ul", attrs={"class": "table-of-contents"})

        for h_tag in toc["h_tags"]:
            li = soup.new_tag("li", attrs={"class": f"toc-{h_tag.name}"})
            a = soup.new_tag("a", href=f"#{h_tag.attrs['id']}")
            a.string = h_tag.get_text()
            li.append(a)
            ul.append(li)

        toc["p_tag"].append(ul)

    return soup.prettify()
