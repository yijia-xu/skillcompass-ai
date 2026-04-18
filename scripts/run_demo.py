import json
from pathlib import Path

from pypdf import PdfReader

from src.services.analyze import run_analysis
from src.services.formatters import result_to_markdown


def load_resume_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    resume_path = root / "examples" / "sample_resume.txt"
    output_json = root / "examples" / "sample_output.json"
    output_md = root / "examples" / "sample_output.md"

    result = run_analysis(
        target_role="data_engineer",
        resume_text=load_resume_text(resume_path),
    )

    output_json.write_text(json.dumps(result.model_dump(), indent=2, ensure_ascii=True))
    output_md.write_text(result_to_markdown(result))
    print(f"Saved demo outputs to {output_json} and {output_md}")


if __name__ == "__main__":
    main()
