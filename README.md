# Cyclomatic Complexity Analyzer

A multi-language tool to visualize control-flow graphs, calculate
cyclomatic complexity, and explore independent paths.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run dashboard/app.py
```

The Clang C++ frontend and analysis engines must be implemented
and integrated before full analysis is available.
