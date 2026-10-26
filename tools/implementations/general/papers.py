"""One bounded arXiv search/download operation with per-call artifact isolation."""

import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


def download_papers(query: str, max_results: int = 3, download: bool = True) -> dict:
    """Query the arXiv Atom API and optionally download at most10 PDFs.

    query is an explicit arXiv search expression, e.g. all:"graph learning".
    No LLM rewrites or scientific topic inference. Return paper IDs, titles,
    abstracts, canonical URLs and optional task-local PDF paths/SHA256. Each
    request has time and byte limits, uses a unique artifact directory, never
    clears an existing directory, and checks PDF status/content. Partial PDF
    failures remain per-record failures and do not count as downloaded files.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError('query must be a nonempty arXiv search expression <=2000 characters')
    if type(max_results) is not int or not 1 <= max_results <= 10 or type(download) is not bool:
        raise ValueError('max_results must be an integer1..10 and download a Boolean')
    import requests
    with requests.Session() as session:
        response = session.get('https://export.arxiv.org/api/query', params={'search_query': query, 'start': 0, 'max_results': max_results}, timeout=(10, 45))
        response.raise_for_status()
        if len(response.content) > 4 * 1024 * 1024:
            raise ValueError('arXiv response exceeds4MiB')
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as error:
            raise ValueError('arXiv did not return a valid Atom document') from error
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        if root.tag != '{http://www.w3.org/2005/Atom}feed':
            raise ValueError('arXiv response is not an Atom feed')
        directory = None
        if download:
            from .research_data import _task_artifacts_root
            import uuid
            directory = _task_artifacts_root() / 'arxiv' / uuid.uuid4().hex
            directory.mkdir(parents=True)
        papers = []
        for entry in root.findall('a:entry', ns)[:max_results]:
            identity = (entry.findtext('a:id', '', ns) or '').strip()
            parsed = urlparse(identity)
            if parsed.hostname not in {'arxiv.org', 'www.arxiv.org'} or not parsed.path.startswith('/abs/'):
                raise ValueError('Unexpected arXiv paper identifier')
            identifier = parsed.path[len('/abs/'):]
            url = 'https://export.arxiv.org/pdf/' + identifier
            row = dict(id=identifier, title=' '.join(entry.findtext('a:title', '', ns).split()), abstract=entry.findtext('a:summary', '', ns).strip(), abstract_url='https://arxiv.org/abs/' + identifier, pdf_url='https://arxiv.org/pdf/' + identifier, download_url=url, download_status='not_requested')
            if download:
                target = directory / (hashlib.sha256(identifier.encode()).hexdigest()[:20] + '.pdf')
                temporary = target.with_suffix('.tmp')
                try:
                    with session.get(url, timeout=(10, 60), stream=True) as pdf:
                        pdf.raise_for_status()
                        size, sha, header = 0, hashlib.sha256(), b''
                        with temporary.open('wb') as handle:
                            for chunk in pdf.iter_content(chunk_size=65536):
                                if not chunk:
                                    continue
                                header = (header + chunk)[:5]
                                if len(header) == 5 and header != b'%PDF-':
                                    raise ValueError('PDF endpoint returned non-PDF content')
                                size += len(chunk)
                                if size > 50 * 1024 * 1024:
                                    raise ValueError('PDF exceeds50MiB')
                                sha.update(chunk)
                                handle.write(chunk)
                        if size < 5:
                            raise ValueError('PDF endpoint returned empty/truncated content')
                        temporary.replace(target)
                    row.update(download_status='downloaded', pdf_file=str(target), pdf_sha256=sha.hexdigest(), bytes=size)
                except (requests.RequestException, OSError, ValueError) as error:
                    temporary.unlink(missing_ok=True)
                    row.update(download_status='failed', error_type=type(error).__name__, error=str(error))
            papers.append(row)
        failed_all = bool(download and papers and all(row['download_status'] == 'failed' for row in papers))
        return dict(status='error' if failed_all else 'success', error='All PDF downloads failed; inspect per-paper failures.' if failed_all else None, query=query, records=papers, returned_count=len(papers), downloaded_count=sum(row['download_status']=='downloaded' for row in papers), source='arXiv Atom API', scope='Search and file retrieval only; no paper quality or scientific conclusion inferred')
