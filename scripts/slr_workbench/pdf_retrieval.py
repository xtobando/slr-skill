"""Download a public PDF from a supported repository into a new local folder."""

import hashlib
import re
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .search.archive import save
from .search.http import NoRedirect

ARXIV_ID = r"(?:\d{4}\.\d{4,5}|[a-z][a-z.\-]*/\d{7})(?:v\d+)?"


def retrieve_pdf(output, arxiv, pmc):
    if arxiv and re.fullmatch(ARXIV_ID, arxiv):
        urls = [f"https://arxiv.org/pdf/{arxiv}"]
    elif pmc and re.fullmatch(r"PMC\d+", pmc):
        urls = [f"https://europepmc.org/articles/{pmc}?pdf=render"]
    else:
        raise ValueError("Supply an arXiv ID or a PMCID, such as PMC12345.")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Choose a new retrieval directory.")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Keep redirects off by default, except HTTPS redirects to these repository hosts.
    class PublicRepositoryRedirect(NoRedirect):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            from urllib.request import HTTPRedirectHandler

            url = urlsplit(newurl)
            if (
                url.scheme == "https"
                and url.netloc in {"europepmc.org", "www.ebi.ac.uk", "arxiv.org"}
                and url.netloc == urlsplit(req.full_url).netloc
            ):
                return HTTPRedirectHandler.redirect_request(
                    self, req, fp, code, msg, headers, newurl
                )
            return None

    url = urls[0]
    with tempfile.TemporaryDirectory(prefix=".pdf-download-", dir=output.parent) as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        try:
            request = Request(
                url, headers={"Accept": "application/pdf", "User-Agent": "slr-workbench"}
            )
            with build_opener(PublicRepositoryRedirect()).open(request, timeout=30) as response:
                final_url = response.geturl()
                digest, total = hashlib.sha256(), 0
                with (staged / "original.pdf").open("wb") as stream:
                    header = response.read(1024)
                    if not header.startswith(b"%PDF-"):
                        raise ValueError(
                            "The repository returned no usable PDF. Supply an authorized local copy."
                        )
                    stream.write(header)
                    digest.update(header)
                    total = len(header)
                    while chunk := response.read(65536):
                        total += len(chunk)
                        if total > 100 * 1024 * 1024:
                            raise ValueError("PDF exceeds the 100 MiB retrieval limit.")
                        digest.update(chunk)
                        stream.write(chunk)
        except (URLError, TimeoutError):
            raise ValueError(
                "Repository PDF unavailable. Check the identifier or supply a local copy."
            ) from None
        receipt = {
            "source_url": url,
            "final_url": final_url,
            "sha256": digest.hexdigest(),
            "bytes": total,
            "file": "original.pdf",
        }
        save(staged / "retrieval.json", receipt)
        if output.exists():
            raise FileExistsError("Choose a new retrieval directory.")
        staged.rename(output)
    return {"pdf": str(output / "original.pdf"), "receipt": str(output / "retrieval.json")}
