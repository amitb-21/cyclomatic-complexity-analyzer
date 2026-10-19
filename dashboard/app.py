import os
import sys
import tempfile
import textwrap
from pathlib import Path

import graphviz
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_paths
from frontend.cpp.parser import CppParser
from frontend.python.parser import PythonParser
from frontend.java import JavaParser


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Multi-Language Code Complexity Analyzer",
    page_icon=":material/account_tree:",
    layout="wide",
)


# --------------------------------------------------
# SAMPLE CODE
# --------------------------------------------------

DEFAULT_CODE = """int analyze(int values[], int size) {
    int total = 0;

    for (int i = 0; i < size; i++) {
        if (values[i] < 0) {
            continue;
        }

        if (values[i] == 999) {
            break;
        }

        total += values[i];
    }

    return total;
}"""


PYTHON_DEFAULT_CODE = """def analyze(values):
    total = 0

    for value in values:
        if value < 0:
            continue

        if value == 999:
            break

        total += value

    return total
"""


JAVA_DEFAULT_CODE = """public class BinarySearch {
    public static int binarySearch(int[] arr, int target) {
        int left = 0;
        int right = arr.length - 1;

        while (left <= right) {
            int mid = left + (right - left) / 2;

            if (arr[mid] == target) {
                return mid;
            } else if (arr[mid] < target) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        return -1;
    }
}
"""


# --------------------------------------------------
# LANGUAGE CONFIGURATION
# --------------------------------------------------

PARSER_CONFIG = {
    "C++": (CppParser, ".cpp"),
    "Python": (PythonParser, ".py"),
    "Java": (JavaParser, ".java"),
}


# --------------------------------------------------
# SOURCE ANALYSIS
# --------------------------------------------------

def analyze_source(source: str, language: str):
    parser_class, suffix = PARSER_CONFIG[language]
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            delete=False,
        ) as source_file:
            source_file.write(source.encode("utf-8"))
            temp_path = source_file.name

        cfg = parser_class().build_cfg(temp_path)
        complexity = calculate_complexity(cfg)
        paths = find_independent_paths(cfg)

        return cfg, complexity, paths

    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.remove(temp_path)


# --------------------------------------------------
# CONTROL-FLOW GRAPH VISUALIZATION
# --------------------------------------------------

def generate_graphviz(cfg):
    dot = graphviz.Digraph(
        "ControlFlowGraph",
        engine="dot",
    )

    dot.attr(
        "graph",
        rankdir="TB",
        bgcolor="transparent",
        pad="0.18",
        nodesep="0.24",
        ranksep="0.34",
        splines="polyline",
    )

    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fontname="monospace",
        fontsize="9",
        margin="0.14,0.09",
        color="#a8b9b8",
        fontcolor="#213536",
        fillcolor="#f2f7f5",
    )

    dot.attr(
        "edge",
        color="#708684",
        fontname="sans-serif",
        fontsize="10",
        arrowsize="0.7",
    )

    # Draw CFG nodes.
    # Branch-gate nodes are hidden to avoid displaying
    # separate True branch / False branch boxes.
    for node_id, node in cfg.nodes.items():

        if node.label in {"True branch", "False branch"}:
            dot.node(
                str(node_id),
                label="",
                shape="point",
                style="invis",
                width="0.01",
                height="0.01",
            )
            continue

        label = "\n".join(
            textwrap.wrap(
                node.label,
                width=34,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )

        if node.label == "Entry":
            dot.node(
                str(node_id),
                label,
                shape="oval",
                fillcolor="#dff2e7",
                color="#5b9b72",
            )

        elif node.label == "Exit":
            dot.node(
                str(node_id),
                label,
                shape="oval",
                fillcolor="#f8e7e3",
                color="#c77c6d",
            )

        else:
            dot.node(str(node_id), label)

    # Draw edges with branch labels.
    edge_labels = getattr(cfg, "edge_labels", {})

    for source, target in cfg.get_edges():
        label = edge_labels.get((source, target), "")

        if not label:
            source_node = cfg.nodes.get(source)
            target_node = cfg.nodes.get(target)

            source_label = getattr(source_node, "label", "")
            target_label = getattr(target_node, "label", "")

            is_control_transfer = source_label in {
                "break;",
                "continue;",
            }

            if (
                target_label.startswith("Case ")
                or target_label == "Default"
            ):
                label = target_label

            elif not is_control_transfer:

                if target_label in {
                    "True branch",
                    "For body",
                    "While body",
                    "Do-while body",
                }:
                    label = "True"

                elif target_label in {
                    "False branch",
                    "After for",
                    "After while",
                    "After do-while",
                }:
                    label = "False"

        edge_style = {}

        if label == "True":
            label = "TRUE"
            edge_style = {
                "color": "#69d99a",
                "fontcolor": "#69d99a",
                "fontsize": "11",
                "penwidth": "1.4",
            }

        elif label == "False":
            label = "FALSE"
            edge_style = {
                "color": "#ff9385",
                "fontcolor": "#ff9385",
                "fontsize": "11",
                "penwidth": "1.4",
            }

        elif label == "Back":
            label = "BACK"

        dot.edge(
            str(source),
            str(target),
            label=label,
            **edge_style,
        )

    return dot


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.header(
        "Analysis guide",
        icon=":material/query_stats:",
    )

    st.markdown("**Cyclomatic complexity**")
    st.latex(r"M = E - N + 2P")

    st.caption(
        "E = edges, N = nodes, P = connected components."
    )

    st.markdown("**Independent paths**")

    st.caption(
        "Paths are selected from bounded Entry-to-Exit walks. "
        "For unusually large graphs, the path search may "
        "return an incomplete basis."
    )

    st.divider()

    st.markdown("**Supported languages**")
    st.markdown("- C++")
    st.markdown("- Python")
    st.markdown("- Java")


# --------------------------------------------------
# MAIN PAGE
# --------------------------------------------------

st.title(
    "Multi-Language Code Complexity Analyzer",
    icon=":material/account_tree:",
)

st.caption(
    "Analyze cyclomatic complexity, explore independent "
    "paths, and visualize control-flow graphs for C++, Python, and Java."
)


# --------------------------------------------------
# LANGUAGE SELECTOR
# --------------------------------------------------

language = st.segmented_control(
    "Language",
    options=["C++", "Python", "Java"],
    default="C++",
    key="selected_language",
)

sample_by_language = {
    "C++": DEFAULT_CODE,
    "Python": PYTHON_DEFAULT_CODE,
    "Java": JAVA_DEFAULT_CODE,
}

source_key = (
    f"source_{language.lower().replace('+', 'p')}"
)

if source_key not in st.session_state:
    st.session_state[source_key] = sample_by_language[language]

if language == "Python":
    st.caption(
        "Analyzes functions plus module/class initialization, including "
        "branches, loops, match, assertions, exception handling, and "
        "conditional expressions. Exception flow is approximate."
    )
elif language == "Java":
    st.caption(
        "Analyzes methods, constructors, and initializers with branches, "
        "loops, switch, assertions, ternaries, and try/catch/finally. "
        "Exception flow is approximate."
    )


# --------------------------------------------------
# CODE EDITOR AND ANALYZE BUTTON
# --------------------------------------------------

with st.form("source_form"):

    code_input = st.text_area(
        f"{language} source code",
        height=330,
        key=source_key,
        help=(
            "The analyzer parses source code; "
            "it does not compile or execute it."
        ),
    )

    submitted = st.form_submit_button(
        "Analyze code",
        type="primary",
        icon=":material/analytics:",
        width="stretch",
    )


# --------------------------------------------------
# ANALYSIS STATE
# --------------------------------------------------

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "analysis_error" not in st.session_state:
    st.session_state.analysis_error = None


# --------------------------------------------------
# RUN ANALYSIS
# --------------------------------------------------

if submitted:
    st.session_state.analysis_result = None
    st.session_state.analysis_error = None

    if not code_input.strip():
        st.session_state.analysis_error = (
            f"Enter {language} source code before analyzing."
        )

    else:
        try:
            with st.spinner(
                "Building the control-flow graph and calculating results..."
            ):
                cfg, complexity, paths = analyze_source(
                    code_input,
                    language,
                )

            st.session_state.analysis_result = {
                "source": code_input,
                "language": language,
                "cfg": cfg,
                "complexity": complexity,
                "paths": paths,
            }

        except (OSError, TypeError, ValueError) as error:
            st.session_state.analysis_error = str(error)

        except Exception as error:
            st.session_state.analysis_error = (
                f"Analysis failed: {error}"
            )


# --------------------------------------------------
# DISPLAY ERRORS
# --------------------------------------------------

if st.session_state.analysis_error:
    st.error(
        st.session_state.analysis_error,
        icon=":material/error:",
    )


# --------------------------------------------------
# DISPLAY RESULTS
# --------------------------------------------------

result = st.session_state.analysis_result

if result is not None:

    if (
        code_input != result["source"]
        or language != result["language"]
    ):
        st.info(
            "The source or language has changed. "
            "Analyze again to refresh these results."
        )

    cfg = result["cfg"]
    complexity = result["complexity"]
    paths = result["paths"]

    # Metrics
    st.subheader("Analysis results")

    with st.container(horizontal=True):
        st.metric(
            "Cyclomatic complexity",
            complexity["complexity"],
            border=True,
        )

        st.metric(
            "Independent paths",
            len(paths),
            border=True,
        )

        st.metric(
            "CFG nodes",
            complexity["nodes"],
            border=True,
        )

        st.metric(
            "CFG edges",
            complexity["edges"],
            border=True,
        )

    st.caption(
        f"M = {complexity['edges']} - {complexity['nodes']} "
        f"+ 2({complexity['components']}) "
        f"= {complexity['complexity']}"
    )

    if len(paths) < complexity["complexity"]:
        st.warning(
            f"The bounded path search found {len(paths)} "
            f"independent paths, while the graph's complexity "
            f"is {complexity['complexity']}. "
            "The displayed path basis may be incomplete "
            "for this graph.",
            icon=":material/warning:",
        )

    # Control-flow graph
    st.header(
        "Control-flow graph",
        icon=":material/account_tree:",
    )

    st.caption(
        ":green[TRUE] enters the branch or loop body. "
        ":red[FALSE] takes an else branch or exits a loop. "
        "`BACK` rechecks a loop condition after its update."
    )

    dot = generate_graphviz(cfg)

    _, graph_viewer, _ = st.columns([1, 2, 1])

    with graph_viewer:
        st.graphviz_chart(
            dot,
            width="stretch",
            height=560,
            alt=(
                f"Control-flow graph from the submitted "
                f"{result['language']} source"
            ),
        )

    st.download_button(
        "Download Graphviz source",
        data=dot.source,
        file_name="control_flow_graph.dot",
        mime="text/vnd.graphviz",
        icon=":material/download:",
    )

    # Independent paths
    st.header(
        "Linear independent paths",
        icon=":material/route:",
    )

    if not paths:
        st.info(
            "No Entry-to-Exit paths were found in this graph."
        )

    else:
        for index, path in enumerate(paths, start=1):

            with st.expander(
                f"Path {index} · {len(path)} steps",
                expanded=(index == 1),
            ):
                path_text = "\n".join(
                    f"{step}. {label}"
                    for step, label in enumerate(
                        path,
                        start=1,
                    )
                )

                st.code(
                    path_text,
                    language=None,
                    wrap_lines=True,
                    width="stretch",
                )