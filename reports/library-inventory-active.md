# Python Library Inventory

- **Observation date:** 2026-11-12T15:39:34Z
- **Python version:** 3.11.18
- **Probe suite version:** 0.1.0
- **Catalog version:** 1.1
- **Libraries discovered:** 77

## AI

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| openai | 3.46.0 | Official client library for the OpenAI API. | [Documentation](https://platform.openai.com/docs/libraries) |
| tiktoken | 0.14.0 | Fast byte-pair-encoding tokenizer for OpenAI models. | [Documentation](https://github.com/openai/tiktoken) |

## Networking

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| anyio | 4.16.0 | Asynchronous concurrency and networking layer over asyncio and Trio. | [Documentation](https://anyio.readthedocs.io/) |
| h11 | 0.16.0 | Pure-Python, spec-compliant HTTP/1.1 protocol implementation. | [Documentation](https://h11.readthedocs.io/) |
| httpcore | 1.0.9 | Minimal low-level HTTP client that powers the HTTPX transport. | [Documentation](https://www.encode.io/httpcore/) |
| httpx | 0.28.1 | Next-generation HTTP client with sync and async support. | [Documentation](https://www.python-httpx.org/) |
| idna | 3.20 | Internationalized Domain Names in Applications (IDNA) encoding support. | [Documentation](https://github.com/kjd/idna) |
| requests | 2.34.2 | Simple, human-friendly HTTP client for Python. | [Documentation](https://requests.readthedocs.io/) |
| urllib3 | 2.8.0 | Powerful, user-friendly HTTP client library. | [Documentation](https://urllib3.readthedocs.io/) |
| websockets | 17.4 | Library for building WebSocket servers and clients with asyncio. | [Documentation](https://websockets.readthedocs.io/) |

## Security

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| certifi | 2026.10.23 | Curated collection of Mozilla root CA certificates for TLS validation. | [Documentation](https://github.com/certifi/python-certifi) |
| cryptography | 50.0.2 | Cryptographic recipes and primitives for Python. | [Documentation](https://cryptography.io/) |
| PyJWT | 2.15.1 | Encode and decode JSON Web Tokens (JWT). | [Documentation](https://pyjwt.readthedocs.io/) |

## Serialization

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| orjson | 3.13.0 | Fast JSON serialization library implemented in Rust. | [Documentation](https://github.com/ijl/orjson) |
| PyYAML | 6.0.3 | YAML parser and emitter for Python. | [Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) |

## Utilities

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| annotated-types | 0.8.0 | Reusable constraint types for use with typing Annotated. | [Documentation](https://github.com/annotated-types/annotated-types) |
| cffi | 2.1.1 | Foreign Function Interface for calling C code from Python. | [Documentation](https://cffi.readthedocs.io/) |
| charset-normalizer | 3.5.2 | Character-set detection and text encoding normalization. | [Documentation](https://charset-normalizer.readthedocs.io/) |
| click | 8.5.0 | Composable toolkit for building command-line interfaces. | [Documentation](https://click.palletsprojects.com/) |
| packaging | 26.3 | Core utilities for Python package versions, specifiers, and markers. | [Documentation](https://packaging.pypa.io/) |
| pycparser | 3.12 | Complete C99 parser written in pure Python. | [Documentation](https://github.com/eliben/pycparser) |
| pydantic | 2.14.3 | Data validation and settings management using type hints. | [Documentation](https://docs.pydantic.dev/) |
| pydantic-settings | 2.16.2 | Settings management using Pydantic models and environment variables. | [Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| pydantic_core | 2.50.4 | Rust-based validation core that powers Pydantic v2. | [Documentation](https://github.com/pydantic/pydantic-core) |
| python-dotenv | 1.2.4 | Load environment variables from .env files. | [Documentation](https://saurabh-kumar.com/python-dotenv/) |
| typing-inspection | 0.4.5 | Runtime inspection utilities for typing annotations. | [Documentation](https://github.com/pydantic/typing-inspection) |
| typing_extensions | 4.16.0 | Backported and experimental type hints for older Python versions. | [Documentation](https://typing-extensions.readthedocs.io/) |

## Web

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| starlette | 1.10.0 | Lightweight ASGI framework and toolkit that underpins FastAPI. | [Documentation](https://www.starlette.io/) |
| uvicorn | 0.54.0 | Lightning-fast ASGI server implementation. | [Documentation](https://www.uvicorn.org/) |

## New packages (48)

These packages are not yet in the agent-harness-explorer skill's curated catalog (`references/python-library-catalog.yaml`). Descriptions and links below are read from each package's installed metadata.

| Library | Version | Description | Documentation |
| --- | ---: | --- | --- |
| agent-harness | 0.1.0 | Agent Harness agnóstico: MCP, Tool Calling, Permisos y TUI. |  |
| attrs | 26.1.0 | Classes Without Boilerplate | [link](https://www.attrs.org/) |
| coverage | 7.17.2 | Code coverage measurement for Python | [link](https://coverage.readthedocs.io/en/7.17.2) |
| distro | 1.9.0 | Distro - an OS platform information API | [link](https://github.com/python-distro/distro) |
| httpcore2 | 2.16.0 | A minimal low-level HTTP client. | [link](https://github.com/pydantic/httpx2) |
| httpx2 | 2.16.0 | The next generation HTTP client. | [link](https://github.com/pydantic/httpx2) |
| iniconfig | 2.3.1 | brain-dead simple config-ini parsing | [link](https://github.com/pytest-dev/iniconfig) |
| jiter | 0.18.0 | Fast iterable JSON parser. | [link](https://github.com/pydantic/jiter/) |
| jsonpatch | 1.44 | Apply JSON-Patches (RFC 6902) | [link](https://python-json-patch.readthedocs.org/) |
| jsonpointer | 3.10 | Identify specific nodes in a JSON document (RFC 6901) | [link](https://github.com/stefankoegl/python-json-pointer) |
| jsonschema | 4.26.0 | An implementation of JSON Schema validation for Python | [link](https://python-jsonschema.readthedocs.io/) |
| jsonschema-specifications | 2025.9.1 | The JSON Schema meta-schemas and vocabularies, exposed as a Registry | [link](https://jsonschema-specifications.readthedocs.io/) |
| langchain-core | 1.7.6 | Building applications with LLMs through composability | [link](https://reference.langchain.com/python/langchain_core/) |
| langchain-openai | 1.7.4 | An integration package connecting OpenAI and LangChain | [link](https://reference.langchain.com/python/integrations/langchain_openai/) |
| langchain-protocol | 0.0.21 | Python bindings for the LangChain agent streaming protocol | [link](https://github.com/langchain-ai/agent-protocol/tree/main/streaming) |
| langsmith | 0.14.17 | Client library to connect to the LangSmith Observability and Evaluation Platform. | [link](https://github.com/langchain-ai/langsmith-python) |
| linkify-it-py | 2.2.0 | Links recognition library with FULL unicode support. | [link](https://github.com/tsutsu3/linkify-it-py) |
| markdown-it-py | 4.2.0 | Python port of markdown-it. Markdown parsing, done right! | [link](https://markdown-it-py.readthedocs.io) |
| mcp | 2.3.0 | Model Context Protocol SDK | [link](https://py.sdk.modelcontextprotocol.io/) |
| mcp-types | 2.3.0 | Model Context Protocol wire types | [link](https://py.sdk.modelcontextprotocol.io/) |
| mdit-py-plugins | 0.6.1 | Collection of plugins for markdown-it-py | [link](https://mdit-py-plugins.readthedocs.io) |
| mdurl | 0.1.2 | Markdown URL utilities | [link](https://github.com/executablebooks/mdurl) |
| opentelemetry-api | 1.45.2 | OpenTelemetry Python API | [link](https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api) |
| pathlib | 1.0.1 | Object-oriented filesystem paths | [link](https://pathlib.readthedocs.org/) |
| platformdirs | 4.14.5 | A small Python package for determining appropriate platform-specific dirs, e.g. a `user data dir`. | [link](https://platformdirs.readthedocs.io) |
| pluggy | 1.7.0 | plugin and hook calling mechanisms for python | [link](https://pluggy.readthedocs.io/) |
| prompt_toolkit | 3.0.53 | Library for building powerful interactive command lines in Python | [link](https://python-prompt-toolkit.readthedocs.io/en/stable/) |
| Pygments | 2.21.0 | Pygments is a syntax highlighting package written in Python. | [link](https://pygments.org/docs) |
| pyperclip | 1.11.0 | A cross-platform clipboard module for Python. (Only handles plain text for now.) | [link](https://github.com/asweigart/pyperclip) |
| pytest | 9.2.0 | pytest: simple powerful testing with Python | [link](https://docs.pytest.org/en/latest/) |
| pytest-asyncio | 1.4.1.post1 | Pytest support for asyncio | [link](https://pytest-asyncio.readthedocs.io) |
| pytest-cov | 7.1.0 | Pytest plugin for measuring coverage. | [link](https://pytest-cov.readthedocs.io/) |
| python-multipart | 0.0.33 | A streaming multipart parser for Python | [link](https://kludex.github.io/python-multipart/) |
| referencing | 0.37.0 | JSON Referencing + Python | [link](https://referencing.readthedocs.io/) |
| regex | 2026.9.29 | Alternative regular expression module, to replace re. | [link](https://github.com/mrabarnett/mrab-regex) |
| requests-toolbelt | 1.0.0 | A utility belt for advanced users of python-requests | [link](https://toolbelt.readthedocs.io/) |
| rich | 15.0.0 | Render rich text, tables, progress bars, syntax highlighting, markdown and more to the terminal | [link](https://rich.readthedocs.io/en/latest/) |
| rpds-py | 2026.9.1 | Python bindings to Rust's persistent data structures (rpds) | [link](https://rpds.readthedocs.io/) |
| sniffio | 1.3.1 | Sniff out which async library your code is running under | [link](https://sniffio.readthedocs.io/) |
| sse-starlette | 3.6.0 | SSE plugin for Starlette | [link](https://github.com/sysid/sse-starlette) |
| tenacity | 9.2.1 | Retry code until it succeeds | [link](https://tenacity.readthedocs.io) |
| textual | 8.2.8 | Modern Text User Interface framework | [link](https://textual.textualize.io/) |
| tomlscript | 0.2.1 | A lightweight, dependency-free tool to manage your scripts directly from pyproject.toml | [link](https://github.com/phihung/tomlscript) |
| truststore | 0.10.5 | Verify certificates using native system trust stores | [link](https://truststore.readthedocs.io) |
| uuid_utils | 0.19.0 | Fast, drop-in replacement for Python's uuid module, powered by Rust. | [link](https://github.com/aminalaee/uuid-utils) |
| wcwidth | 0.9.4 | Measures the displayed width of unicode strings in a terminal | [link](https://github.com/jquast/wcwidth) |
| xxhash | 4.0.2 | Python binding for xxHash | [link](https://github.com/ifduyue/python-xxhash) |
| zstandard | 0.25.0 | Zstandard bindings for Python | [link](https://python-zstandard.readthedocs.io/en/latest/) |

