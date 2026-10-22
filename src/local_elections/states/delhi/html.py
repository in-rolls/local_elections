"""Read MyNeta's visible fields and statically encoded table rows, offline."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"div", "br", "h2", "h3", "h5", "td", "tr", "p"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"div", "h2", "h3", "h5", "td", "tr", "p"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def text(html):
    parser = VisibleHTML()
    parser.feed(html)
    return "\n".join(
        line
        for part in "".join(parser.parts).splitlines()
        if (line := " ".join(part.split()))
    )


def expand_rows(html):
    """Decode only the site's literal document.write strings; never execute JS."""
    pattern = r'\}\("([^"]+)",\d+,"([^"]+)",(\d+),(\d+),\d+\)\)'
    for match in re.finditer(pattern, html):
        payload, alphabet, offset, base = match.groups()
        radix = int(base)
        digits = {char: str(i) for i, char in enumerate(alphabet)}
        decoded = "".join(
            chr(int("".join(digits[c] for c in token), radix) - int(offset))
            for token in payload.split(alphabet[radix])
            if token
        )
        if not (decoded.startswith("document.write('") and decoded.endswith("');")):
            raise ValueError("Unexpected encoded script; refusing to execute it")
        html += decoded[len("document.write('") : -len("');")].replace("\\'", "'")
    return html


def ward_key(label, year):
    pattern = (
        r"(?:WARD\s*)?(\d+)\s*-\s*([NSE])(?:\s*-|\b)"
        if year == 2017
        else r"(?:WARD\s*)?(\d+)"
    )
    match = re.match(pattern, label.strip(), re.I)
    if not match:
        raise ValueError(f"Unrecognized ward: {label}")
    return f"{int(match[1])}-{match[2].upper()}" if year == 2017 else str(int(match[1]))


def winner_links(html, year, url):
    rows = []
    folder = {2012: "mcd2012", 2017: "delhi2017", 2022: "Delhi2022"}[year]
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", expand_rows(html), re.S | re.I):
        links = re.findall(
            r"href\s*=\s*['\"]?([^\s>'\"]*candidate\.php\?candidate_id=\d+)", row
        )
        links = [link for link in links if folder.lower() in link.lower()]
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
        if links and len(cells) == 8:
            rows.append(
                {
                    "year": year,
                    "ward_number": ward_key(text(cells[2]), year),
                    "listed_name": text(cells[1]),
                    "profile_url": urljoin(url, links[-1]),
                    "list_education": text(cells[5]),
                    "list_cases": text(cells[4]),
                }
            )
    keys = [(r["year"], r["ward_number"]) for r in rows]
    if len(set(keys)) != len(keys) or not rows:
        raise ValueError("Winner list has duplicate wards or no parsed rows")
    return rows


def case_entries(html, heading):
    match = re.search(
        heading + r"</h3>(?:\s|</?div[^>]*>)*<table\b[^>]*>(.*?)</table>",
        html,
        re.S | re.I,
    )
    if not match:
        return None
    serials = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", match[1], re.S | re.I):
        cell = re.search(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
        if cell and text(cell[1]).isdigit():
            serials.append(int(text(cell[1])))
    if not serials and "No Cases" not in text(match[1]):
        raise ValueError("Unrecognized case table")
    if serials and sorted(serials) != list(range(1, len(serials) + 1)):
        raise ValueError("Case serials are not consecutive")
    return len(serials)


def profile(html, year):
    html = expand_rows(html)
    visible = text(html)
    title = re.search(r"<h2\b[^>]*>(.*?)</h2>", html, re.S | re.I)
    ward = re.search(r"<h5\b[^>]*>(.*?)</h5>", html, re.S | re.I)
    if not title or not ward:
        raise ValueError("Missing candidate or ward heading")
    candidate = text(title[1]).splitlines()[-1]
    if "(Winner)" not in candidate:
        raise ValueError(f"Profile does not identify an elected winner: {candidate}")
    education = re.search(r"Educational Details\s+Category:\s*([^\n]+)", visible)
    age = re.search(r"\bAge:\s*(\d+)\b", visible)
    case = re.search(r"\['Cases',\s*(\d+)\]", html)
    pending_sections = [
        case_entries(html, "Cases where " + label)
        for label in ["accused", "charges framed", "Cognizance taken", "Pending"]
    ]
    known_pending = [value for value in pending_sections if value is not None]
    pending = sum(known_pending) if known_pending else None
    convicted = case_entries(html, "Cases where convicted")
    if case and int(case[1]) == 0 and "No criminal cases" in visible:
        pending, convicted = 0, 0
    if (
        case
        and pending is not None
        and convicted is not None
        and pending + convicted != int(case[1])
    ):
        raise ValueError("Case table counts disagree with the displayed total")
    party = re.search(r"\bParty:\s*([^\n]+)", visible)
    occupation = re.search(r"Self Profession:\s*([^\n]+)", visible)
    return {
        "year": year,
        "ward_number": ward_key(text(ward[1]), year),
        "profile_party": party[1].strip() if party else None,
        "profile_name": candidate.replace("(Winner)", "").strip(),
        "education": education[1].strip() if education else None,
        "age": int(age[1]) if age else None,
        "pending_cases": pending,
        "convicted_cases": convicted,
        "occupation": occupation[1].strip() if occupation else None,
    }
