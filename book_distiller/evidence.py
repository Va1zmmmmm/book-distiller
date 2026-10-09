"""Exact source spans; adapted from the project's quote_sources.py."""
import hashlib

OMISSION = '[……]'

class InvalidInput(ValueError):
    """A user input or generated response cannot be safely consumed."""

def sha(data):
    return hashlib.sha256(data).hexdigest()

def exact_spans(quote, source):
    if not isinstance(quote, str) or not quote.strip():
        return None
    parts = quote.split(OMISSION)
    if any(not p.strip() for p in parts):
        return None
    spans, offset = [], 0
    for part in parts:
        start = source.find(part, offset)
        if start < 0:
            return None
        end = start + len(part)
        spans.append({'start': start, 'end': end,
                      'line_start': source.count('\n', 0, start) + 1,
                      'line_end': source.count('\n', 0, end - 1) + 1})
        offset = end
    return spans

def required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f'{field} 必须是非空字符串')
    return value

def string_list(value, field, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise InvalidInput(f'{field} 必须是{"非空" if nonempty else ""}字符串列表')
    for item in value:
        required_string(item, field)
    return value
