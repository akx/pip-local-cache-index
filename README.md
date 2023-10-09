# pip-local-cache-index

This small tool extracts .whl files from the HTTP cache files in your local Pip cache
to another directory to allow for local installs (e.g. when you're mostly offline but
want to start a new virtualenv with some of the packages you've installed in the past).

## Usage

Basic usage:

```
python pip_local_cache_index.py --dest-dir=./wheels
```

will extract all wheels available to `./wheels`.

You can also use one (or more) `--select='flask*'` style glob patterns to limit what
is extracted, but practically you'll want everything, because dependencies.

After you have a nice wheelhouse, you can do e.g.

```
pip install black==23.9.1 ruff --find-links=./wheels --no-index
```

in your project venv and you're off to the races...
