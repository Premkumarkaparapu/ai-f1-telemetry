import ast

files = [
    'data_pipeline/ingest_all_sessions.py',
    'data_pipeline/bulk_load.py',
    'data_pipeline/fill_telemetry.py',
    'backend/app/api/v1/auth.py',
    'backend/app/api/v1/sessions.py',
    'backend/app/api/v1/telemetry.py',
]
for f in files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f'OK: {f}')
    except SyntaxError as e:
        print(f'SYNTAX ERROR in {f}: {e}')
    except UnicodeDecodeError:
        with open(f, encoding='latin-1') as fh:
            try:
                ast.parse(fh.read())
                print(f'OK (latin-1): {f}')
            except SyntaxError as e:
                print(f'SYNTAX ERROR in {f}: {e}')
