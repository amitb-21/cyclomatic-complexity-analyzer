from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

from engine.complexity import calculate_complexity
from analyze import get_parser_for_file
from frontend.java.parser import JavaParser

# Expected complexities use the convention that each independent branch
# outcome contributes one decision beyond the base complexity of one.
TEST_CASES = [
("Straight-line", '''class Example { int f(int a,int b) { int x=a+b; return x*2; } }''', 1),
("Single if", '''class Example { int f(int n) { if(n<0) return -n; return n; } }''', 2),
("If-else", '''class Example { String f(int n) { if(n%2==0) return "even"; else return "odd"; } }''', 2),
("Nested if", '''class Example { int f(int n) { if(n>0) { if(n>10) return 2; return 1; } return 0; } }''', 3),
("Else-if ladder", '''class Example { int f(int n) { if(n>90)return 1; else if(n>75)return 2; else if(n>60)return 3; else return 4; } }''', 4),
("For loop", '''class Example { int f(int n) { int s=0; for(int i=0;i<n;i++) s+=i; return s; } }''', 2),
("While loop", '''class Example { int f(int n) { while(n>0) n--; return n; } }''', 2),
("Do-while", '''class Example { int f(int n) { do { n--; } while(n>0); return n; } }''', 2),
("Nested loops", '''class Example { int f(int n) { int s=0; for(int i=0;i<n;i++) for(int j=0;j<n;j++) s++; return s; } }''', 3),
("Switch", '''class Example { int f(int n) { switch(n) { case 1:return 1; case 2:return 2; default:return 0; } } }''', 3),
("Boolean && and ||", '''class Example { boolean f(int a, boolean b, boolean c) { if(a>0 && b || c)return true; return false; } }''', 4),
("Try-catch-finally", '''class Example { int f(String s) { try { return Integer.parseInt(s); } catch(NumberFormatException e) { return -1; } finally { System.out.println("done"); } } }''', 2),
("Throw with if", '''class Example { int f(int n) { if(n<0) throw new IllegalArgumentException(); return n; } }''', 2),
("Break and continue", '''class Example { int f(int n) { int x=0; for(int i=0;i<n;i++){ if(i%2==1)continue; if(i>10)break; x=i; } return x; } }''', 4),
("Ternary", '''class Example { int f(int a,int b) { return a>b ? a : b; } }''', 2),
("Enhanced for", '''class Example { int f(int[] a) { int s=0; for(int x:a)s+=x; return s; } }''', 2),
("Nested loops plus if", '''class Example { int f(int[][] a,int t) { for(int i=0;i<a.length;i++) for(int j=0;j<a[i].length;j++) if(a[i][j]==t)return 1; return 0; } }''', 4),
("Synchronized block", '''class Example { Object lock=new Object(); void f(){ synchronized(lock) { System.out.println("x"); } } }''', 1),
("Constructor and initializer", '''class Example { int x; { x=1; } Example(){ if(x<0)x=0; } int get(){return x;} }''', 4),
("Multiple methods", '''class Example { int a(int x){if(x>0)return x;return 0;} int b(int x){while(x>0)x--;return x;} int c(){return 42;} }''', 5),
("Recursion", '''class Example { int f(int n){if(n<=1)return 1;return n*f(n-1);} }''', 2),
("Nested plain blocks", '''class Example { int f(int n){{int x=n+1;{int y=x*2;n=y-1;}}return n;} }''', 1),
("Combined loop and nested decisions", '''class Example { int f(int[] a){int r=0;for(int x:a){if(x>0){if(x%2==0)r++;}}return r;} }''', 4),
("Empty method", '''class Example { void f(){} }''', 1),
]

def main():
    parser = JavaParser()
    passed = failed = 0
    with TemporaryDirectory(prefix="java_complexity_tests_") as tmp:
        root = Path(tmp)
        for i, (name, source, expected) in enumerate(TEST_CASES, 1):
            path = root / f"Case{i:02}.java"
            path.write_text(source + "\n", encoding="utf-8")
            print(f"\n{i:02}. {name}")
            try:
                cfg = parser.build_cfg(str(path))
                result = calculate_complexity(cfg)
                actual = result["complexity"]
                print(f"    complexity={actual}, nodes={result['nodes']}, edges={result['edges']}")
                if actual == expected:
                    passed += 1
                    print(f"    PASS (expected {expected})")
                else:
                    failed += 1
                    print(f"    FAIL (expected {expected})")
            except Exception as exc:
                failed += 1
                print(f"    ERROR: {type(exc).__name__}: {exc}")
    print(f"\nSUMMARY: {passed} passed, {failed} failed/errors; {len(TEST_CASES)} total")
    if failed:
        raise SystemExit(1)

if __name__ == "__main__":
    main()

def test_java_complexity_examples():
    main()


def test_switch_expression_and_short_circuit_paths(tmp_path):
    source = """class Example {
    int choose(int value) {
        return switch (value) {
            case 1 -> 10;
            case 2, 3 -> 20;
            default -> 0;
        };
    }
    boolean check(boolean a, boolean b, boolean c) {
        return a && (b || c) ? true : false;
    }
}
"""
    source_file = tmp_path / "Example.java"
    source_file.write_text(source, encoding="utf-8")

    cfg = JavaParser().build_cfg(str(source_file))

    assert calculate_complexity(cfg)["complexity"] == 7
    assert {"True", "False"}.issubset(set(cfg.edge_labels.values()))
    assert any(label.startswith("case 2") or label.startswith("case 3") for label in cfg.edge_labels.values())


def test_finally_runs_on_return_and_syntax_errors_are_reported(tmp_path):
    source_file = tmp_path / "Finally.java"
    source_file.write_text(
        "class Finally { int f() { try { return 1; } finally { cleanup(); } } }",
        encoding="utf-8",
    )
    cfg = JavaParser().build_cfg(str(source_file))
    cleanup = next(node for node in cfg.nodes.values() if node.label == "cleanup();")
    returns = [node for node in cfg.nodes.values() if node.label == "return 1;"]
    assert returns
    assert all(node.successors == [cleanup] for node in returns)

    source_file.write_text("class Broken { int f( { return 1; } }", encoding="utf-8")
    with pytest.raises(ValueError, match="Java source contains syntax errors"):
        JavaParser().build_cfg(str(source_file))


def test_ternary_in_assignment_and_assertion_are_decisions(tmp_path):
    source_file = tmp_path / "Decisions.java"
    source_file.write_text(
        "class Decisions { int f(int a, int b) { "
        "int max = a > b ? a : b; assert max >= 0; return max; } }",
        encoding="utf-8",
    )

    cfg = JavaParser().build_cfg(str(source_file))

    assert calculate_complexity(cfg)["complexity"] == 3


def test_cli_routes_java_sources_to_java_parser():
    assert isinstance(get_parser_for_file("Program.JAVA"), JavaParser)