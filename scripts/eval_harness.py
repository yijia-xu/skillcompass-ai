import argparse
import json
from pathlib import Path

from src.graph.state import GraphState
from src.graph.workflow import build_workflow


def evaluate_output_shape(result: GraphState) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not result.parsed_resume_skills:
        issues.append("parsed_resume_skills is empty")
    if not result.matched_postings:
        issues.append("matched_postings is empty")
    if not result.top_skill_gaps:
        issues.append("top_skill_gaps is empty")
    if not result.learning_plan:
        issues.append("learning_plan is empty")
    if len(result.learning_plan) < 3:
        issues.append("learning_plan has fewer than 3 phases")
    return (len(issues) == 0, issues)


def run_live_eval(target_role: str, resume_path: Path) -> tuple[bool, list[str], GraphState]:
    resume_text = resume_path.read_text()
    app = build_workflow()
    result = GraphState.model_validate(
        app.invoke(GraphState(target_role=target_role, resume_text=resume_text))
    )
    ok, issues = evaluate_output_shape(result)
    return ok, issues, result


def run_offline_eval(sample_output_path: Path) -> tuple[bool, list[str], GraphState]:
    payload = json.loads(sample_output_path.read_text())
    result = GraphState.model_validate(payload)
    ok, issues = evaluate_output_shape(result)
    return ok, issues, result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 evaluation harness for GapSolver AI")
    parser.add_argument("--mode", choices=["live", "offline"], default="offline")
    parser.add_argument("--target-role", default="data_engineer")
    parser.add_argument("--resume-path", default="examples/sample_resume.txt")
    parser.add_argument("--sample-output-path", default="examples/eval_live_output.json")
    parser.add_argument("--save-live-output", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if args.mode == "live":
        ok, issues, result = run_live_eval(args.target_role, root / args.resume_path)
        if args.save_live_output:
            out = root / "examples" / "eval_live_output.json"
            out.write_text(json.dumps(result.model_dump(), indent=2, ensure_ascii=True))
            print(f"Saved live eval output to {out}")
    else:
        sample_path = root / args.sample_output_path
        if not sample_path.exists():
            raise FileNotFoundError(
                f"Offline eval baseline not found at {sample_path}. "
                "Run with --mode live --save-live-output first."
            )
        ok, issues, result = run_offline_eval(sample_path)

    print("=== Phase 1 Eval Report ===")
    print(f"mode: {args.mode}")
    print(f"target_role: {result.target_role}")
    print(f"skills_extracted: {len(result.parsed_resume_skills)}")
    print(f"postings_retrieved: {len(result.matched_postings)}")
    print(f"top_skill_gaps: {len(result.top_skill_gaps)}")
    print(f"learning_phases: {len(result.learning_plan)}")
    if ok:
        print("status: PASS")
        return

    print("status: FAIL")
    for issue in issues:
        print(f"- {issue}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
