
from frontend.cpp.cfg_builder import CFGBuilder
from visualization.cfg_renderer import render_cfg

code = """
int main() {
    int x = 10;

    if (x > 0) {
        x++;
    } else {
        x--;
    }

    return 0;
}
"""

cfg = CFGBuilder().build(code)
render_cfg(cfg, "output/cfg_graph")
