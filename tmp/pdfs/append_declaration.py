from pathlib import Path

from pypdf import PdfReader, PdfWriter


SOURCE_DIR = Path(
    "/Users/marcelapsilverio/Library/CloudStorage/OneDrive-Pessoal/"
    "Área de Trabalho/nutri/certificados"
)
REGULATION = Path(
    "/Users/marcelapsilverio/Library/CloudStorage/OneDrive-Pessoal/"
    "Área de Trabalho/faculdade/"
    "RES-CEPE-05-2023-REGULA-ATIVIDADES-COMPLEMENTARES.pdf"
)
OUTPUT_DIR = Path(
    "/Users/marcelapsilverio/projetos/tcc_crypto/"
    "output/pdf/certificados_com_declaracao"
)


def select_certificates() -> list[Path]:
    selected: list[Path] = []
    for path in sorted(SOURCE_DIR.glob("*.pdf")):
        if any(year in path.name for year in ("2022", "2023", "2024", "2025")):
            selected.append(path)

    additional_names = (
        "CERTIFICADO_DEDC_3511.pdf",
        "CERTIFICADO_DEDC_1024 2.pdf",
        "CERTIFICADO_DEDC_48972827 2.pdf",
        "certificado-gestao-pi.pdf",
    )
    for name in additional_names:
        path = SOURCE_DIR / name
        if path not in selected:
            selected.append(path)

    older_duplicate_issues = (
        "CERTIFICADO_DEDC_1024.pdf",
        "CERTIFICADO_DEDC_48972827.pdf",
    )
    selected = [
        path for path in selected if path.name not in older_duplicate_issues
    ]
    return selected


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    declaration_reader = PdfReader(REGULATION)
    declaration_page = next(
        (
            page
            for page in declaration_reader.pages
            if "DECLARAÇÃO DE AUTENTICIDADE" in (page.extract_text() or "")
        ),
        None,
    )
    if declaration_page is None:
        raise RuntimeError("The declaration was not found in the supplied PDF.")

    selected = select_certificates()
    if len(selected) != 66:
        raise RuntimeError(f"Expected 66 unique certificates, found {len(selected)}.")

    for source in selected:
        source_reader = PdfReader(source)
        writer = PdfWriter()
        for page in source_reader.pages:
            writer.add_page(page)
        writer.add_page(declaration_page)

        output = OUTPUT_DIR / f"{source.stem}-com-declaracao.pdf"
        writer.add_metadata(
            {
                "/Title": f"{source.stem} - com declaração de autenticidade",
                "/Subject": "Certificado acompanhado da declaração de autenticidade",
            }
        )
        with output.open("wb") as stream:
            writer.write(stream)

        verification_reader = PdfReader(output)
        if len(verification_reader.pages) != len(source_reader.pages) + 1:
            raise RuntimeError(f"Unexpected page count in {output.name}.")
        final_text = verification_reader.pages[-1].extract_text() or ""
        if "DECLARAÇÃO DE AUTENTICIDADE" not in final_text:
            raise RuntimeError(f"Declaration missing from {output.name}.")

    print(f"Created and verified {len(selected)} PDFs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
