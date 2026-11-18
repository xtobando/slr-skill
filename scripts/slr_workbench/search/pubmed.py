"""PubMed record extraction adapted from xtobando/slr-system (MIT)."""

import re
import xml.etree.ElementTree as ET


def parse_articles(body: bytes) -> dict:
    from .http import APIError

    if b"<!entity" in body.lower():
        raise APIError("PubMed XML with custom entities is unsupported.")

    def text(node: ET.Element | None) -> str:
        return " ".join("".join(node.itertext()).split()) if node is not None else ""

    try:
        root = ET.fromstring(body)
        if root.tag != "PubmedArticleSet" or root.find(".//ERROR") is not None:
            raise ValueError
        rows = []
        for item in root.findall("PubmedArticle"):
            article = item.find("MedlineCitation/Article")
            pmid = item.findtext("MedlineCitation/PMID")
            if article is None or not pmid:
                raise ValueError
            ids = {
                node.get("IdType"): node.text
                for node in item.findall("PubmedData/ArticleIdList/ArticleId")
            }
            date = (
                article.findtext("Journal/JournalIssue/PubDate/Year")
                or article.findtext("ArticleDate/Year")
                or article.findtext("Journal/JournalIssue/PubDate/MedlineDate")
                or ""
            )
            year = re.search(r"\b\d{4}\b", date)
            authors = [
                text(author.find("CollectiveName"))
                or " ".join(
                    filter(
                        None,
                        [
                            author.findtext("ForeName") or author.findtext("Initials"),
                            author.findtext("LastName"),
                        ],
                    )
                )
                for author in article.findall("AuthorList/Author")
            ]
            abstract = "\n".join(
                (f"{node.get('Label')}: " if node.get("Label") else "") + text(node)
                for node in article.findall("Abstract/AbstractText")
            )
            rows.append(
                {
                    "pmid": pmid,
                    "title": text(article.find("ArticleTitle")),
                    "abstract": abstract,
                    "authors": authors,
                    "doi": ids.get("doi"),
                    "pmc_id": ids.get("pmc"),
                    "year": int(year[0]) if year else None,
                }
            )
        return {"articles": rows, "xml": body.decode("utf-8")}
    except (ValueError, ET.ParseError, UnicodeError):
        raise APIError("PubMed returned invalid or unsupported article XML.") from None
