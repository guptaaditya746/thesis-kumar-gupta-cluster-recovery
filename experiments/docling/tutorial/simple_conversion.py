from pathlib import Path

from docling.document_converter import DocumentConverter

data_folder = Path(__file__).parent / "../data"
input_doc_path = data_folder / "paper.pdf"
# Pointing to the local file path on your cluster storage
# path = "/mnt/ceph/storage/data-tmp/current/xepi3167/thesis/thesis-kumar-gupta/experiments/docling/data/paper.pdf"

# Initialize the converter
converter = DocumentConverter()

# Pass 'path' instead of the commented-out 'source'
result = converter.convert(input_doc_path)

# Print Markdown to stdout
print(result.document.export_to_markdown())
