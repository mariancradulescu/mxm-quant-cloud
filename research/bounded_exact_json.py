"""Write the existing exact Decimal JSON format without a full-document string."""
from pathlib import Path
from .merge_eur_scenarios import exact_json

def dump(value, stream):
    if isinstance(value, dict):
        if not any(isinstance(v, (dict, list)) for v in value.values()):
            stream.write(exact_json(value)); return
        stream.write('{')
        for i, (key, item) in enumerate(value.items()):
            if i: stream.write(',')
            stream.write(exact_json(key)); stream.write(':'); dump(item, stream)
        stream.write('}')
    elif isinstance(value, list):
        stream.write('[')
        for i, item in enumerate(value):
            if i: stream.write(',')
            dump(item, stream)
        stream.write(']')
    else:
        stream.write(exact_json(value))

def write(path, value):
    with Path(path).open('w', encoding='utf-8', newline='\n', buffering=262144) as stream:
        dump(value, stream); stream.write('\n')

def write_arrays(path, header, arrays):
    """Replace selected array fields with single-pass iterators; preserve key order."""
    with Path(path).open('w', encoding='utf-8', newline='\n', buffering=262144) as stream:
        stream.write('{')
        for i, (key, value) in enumerate(header.items()):
            if i: stream.write(',')
            stream.write(exact_json(key)); stream.write(':')
            if key not in arrays:
                dump(value, stream); continue
            stream.write('[')
            for j, item in enumerate(arrays[key]):
                if j: stream.write(',')
                dump(item, stream)
            stream.write(']')
        stream.write('}\n')
