"""
Incremental PDF writer for Canada IRCC XFA forms.

Uses pyHanko's IncrementalPdfFileWriter to modify ONLY the XFA datasets
stream while preserving ALL original bytes, encryption, and digital
signatures (DocMDP + UR3).

This is critical because IRCC forms are:
  - Encrypted (standard empty password)
  - Digitally certified (DocMDP by IRCC)
  - Reader-Extended (UR3 for save capability in Adobe Reader)

Any full PDF rewrite (pypdf, pikepdf) breaks these signatures.
Only a true incremental update preserves them.
"""
from __future__ import annotations

import io
import logging
import zlib
from pathlib import Path

from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils import generic

logger = logging.getLogger(__name__)


def incremental_xfa_write(
    template_path: str | Path,
    output_path: str | Path,
    updated_xml: bytes,
) -> Path:
    """
    Write updated XFA datasets XML into a PDF using incremental update.

    This preserves the original PDF bytes, encryption, DocMDP certification,
    and UR3 Reader Extension rights. The output file is the original
    template with only the datasets stream object appended.

    Args:
        template_path: Path to the original IRCC PDF template.
        output_path: Where to write the filled PDF.
        updated_xml: The modified XFA datasets XML as UTF-8 bytes.

    Returns:
        Path to the output file.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read template into memory (pyHanko needs seekable stream)
    with open(template_path, "rb") as f:
        stream = io.BytesIO(f.read())

    # Create incremental writer
    writer = IncrementalPdfFileWriter(stream)

    # Authenticate (IRCC forms use empty password)
    auth_result = writer.prev.decrypt("")
    logger.debug("PDF auth: %s", auth_result.status)

    # Navigate to XFA datasets stream
    root = writer.root_ref.get_object()
    acroform = root["/AcroForm"].get_object()
    xfa_arr = acroform["/XFA"]
    if hasattr(xfa_arr, "get_object"):
        xfa_arr = xfa_arr.get_object()

    # Find datasets stream reference
    datasets_obj = None
    for i in range(0, len(xfa_arr), 2):
        name = str(xfa_arr[i])
        if name == "datasets":
            datasets_obj = xfa_arr[i + 1].get_object()
            break

    if datasets_obj is None:
        raise RuntimeError("No 'datasets' stream found in XFA array")

    # Compress the new XML
    compressed = zlib.compress(updated_xml)

    # Update stream data
    datasets_obj._data = updated_xml
    datasets_obj._encoded_data = compressed

    # Update stream dictionary
    datasets_obj[generic.NameObject("/Length")] = generic.NumberObject(
        len(compressed)
    )
    datasets_obj[generic.NameObject("/Filter")] = generic.NameObject(
        "/FlateDecode"
    )

    # Mark object as modified (triggers incremental write)
    container_ref = datasets_obj.container_ref
    writer.mark_update(container_ref)

    # Write output (original bytes + incremental appendage)
    with open(output_path, "wb") as out:
        writer.write(out)

    orig_size = template_path.stat().st_size
    out_size = output_path.stat().st_size
    logger.info(
        "Incremental XFA write: %s -> %s (+%d bytes)",
        template_path.name,
        output_path.name,
        out_size - orig_size,
    )

    return output_path


def read_datasets_xml(template_path: str | Path) -> bytes:
    """
    Read the XFA datasets XML from a template PDF.

    Returns the raw XML bytes (decompressed).
    """
    with open(template_path, "rb") as f:
        stream = io.BytesIO(f.read())

    writer = IncrementalPdfFileWriter(stream)
    writer.prev.decrypt("")

    root = writer.root_ref.get_object()
    acroform = root["/AcroForm"].get_object()
    xfa_arr = acroform["/XFA"]
    if hasattr(xfa_arr, "get_object"):
        xfa_arr = xfa_arr.get_object()

    for i in range(0, len(xfa_arr), 2):
        name = str(xfa_arr[i])
        if name == "datasets":
            ds_obj = xfa_arr[i + 1].get_object()
            return ds_obj.data

    raise RuntimeError("No 'datasets' stream found")
