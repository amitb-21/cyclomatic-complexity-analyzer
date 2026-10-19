# Cyclomatic Complexity Analyzer

A multi-language analyzer that builds control-flow graphs (CFGs), calculates
cyclomatic complexity, and finds a set of linearly independent Entry-to-Exit
paths for C++, Python, and Java source code.

## Features

- Displays the cyclomatic complexity and CFG metrics.
- Renders a Graphviz control-flow graph with branch labels.
- Lists the selected independent paths.
- Provides a Streamlit interface and a command-line entry point.
- Analyzes multiple executable functions or methods in a source file.

## Setup

The project uses Tree-sitter grammars for C++ and Java. C++ preprocessing
requires GCC or Clang when the source contains preprocessor directives.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

To use C++ code that has `#include`, `#define`, or other preprocessor
directives, install GCC or Clang and make its preprocessor available on `PATH`.
To select a specific compiler executable, set `CXX` before starting the app:

```powershell
$env:CXX = "C:\MinGW\bin\g++.exe"
```

## Run the app

```powershell
python -m streamlit run dashboard/app.py
```

Choose a language, enter or edit its source code, and select **Analyze code**.
The results include the complexity, graph, and independent paths.

## Command-line use

Pass a source file to `analyze.py`; the parser is selected from the file
extension:

```powershell
python analyze.py examples\kadane.cpp
python analyze.py examples\python_example.py
python analyze.py examples\BinarySearch.java
```

The command prints the complexity and paths and generates a CFG image in the
current directory.

## Supported analysis

Each language frontend maps supported constructs to the shared CFG model:

- **C++** — Tree-sitter C++ grammar. Supports function definitions, `if`,
  `switch`, `for`, `while`, `do-while`, `break`, `continue`, `goto`, labels,
  and short-circuit `&&` / `||`. When source contains preprocessor directives,
  GCC or Clang preprocesses the file. Macros from included headers can expand
  in the analyzed source; included-header implementation code is excluded from
  its CFG.
- **Python** — the standard-library AST. Supports functions, module and class
  initialization statements, `if`, `for`, `while`, `match`, `assert`,
  `try` / `except` / `finally`, `return`, `raise`, `break`, `continue`,
  Boolean short-circuit expressions, and conditional expressions.
- **Java** — Tree-sitter Java grammar. Supports methods, constructors,
  initializer blocks, `if`, loops, `switch` statements and expressions,
  `try` / `catch` / `finally`, `assert`, `return`, `throw`, `break`,
  `continue`, short-circuit conditions, and ternary expressions.

For source files with multiple executable functions or methods, the displayed
complexity is the sum of the individual CFG complexities. The generated graph
joins those regions under a shared Entry and Exit.

## Accuracy and limitations

This project is a source-analysis tool, not a compiler. It does not compile or
execute programs, and it cannot guarantee accurate results for every valid
program. Constructs not listed above, language-specific runtime behavior,
dynamic dispatch, and implicit exception behavior may be simplified or omitted.
Exception edges are approximations, not type-accurate runtime modeling.

Independent paths are selected from bounded Entry-to-Exit walks. For large or
highly cyclic CFGs, path search may not find a complete basis. Review the
generated CFG and paths when correctness is important.

C++ preprocessing runs only when preprocessor directives are present and
requires GCC or Clang to be available on `PATH` or selected through `CXX`.
Preprocessing has a 30-second limit; failures are reported rather than silently
falling back to parsing unexpanded source.

## Tests

Run the regression suite from the project root:

```powershell
python -m pytest
```
