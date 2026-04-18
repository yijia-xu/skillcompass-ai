import gradio as gr
from pypdf import PdfReader

from src.services.analyze import run_analysis
from src.services.formatters import result_to_markdown


def _resolve_file_path(resume_file) -> str:
    if isinstance(resume_file, str):
        return resume_file
    if isinstance(resume_file, dict):
        path = resume_file.get("path") or resume_file.get("name")
        return path if isinstance(path, str) else ""
    path = getattr(resume_file, "name", "")
    return path if isinstance(path, str) else ""


def _extract_resume_text(file_path: str) -> str:
    if not file_path:
        raise ValueError("Please upload a PDF resume.")
    reader = PdfReader(file_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError("Uploaded PDF has no extractable text.")
    return text


def analyze_resume(target_role: str, resume_file):
    try:
        file_path = _resolve_file_path(resume_file)
        resume_text = _extract_resume_text(file_path)
        result = run_analysis(
            target_role=target_role,
            resume_text=resume_text,
            resume_file_path=file_path,
        )
        return result_to_markdown(result)
    except Exception as exc:
        return f"❌ Analyze failed: {exc}"


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="GapSolver AI") as demo:
        gr.Markdown("# GapSolver AI\nUpload a PDF resume to analyze skill gaps against recent market demand.")
        with gr.Row():
            target_role = gr.Textbox(
                label="Target Role",
                value="data_engineer",
                placeholder="e.g. data_engineer",
            )
        resume_file = gr.File(
            label="Resume PDF",
            file_types=[".pdf"],
            type="filepath",
        )
        run_btn = gr.Button("Analyze", variant="primary")
        markdown_output = gr.Markdown(label="Learning Plan")

        run_btn.click(
            fn=analyze_resume,
            inputs=[target_role, resume_file],
            outputs=[markdown_output],
        )

    return demo


if __name__ == "__main__":
    build_ui().launch(server_name="0.0.0.0", server_port=7860)
