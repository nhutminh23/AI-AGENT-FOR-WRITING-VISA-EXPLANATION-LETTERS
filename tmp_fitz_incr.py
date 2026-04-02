import fitz
import shutil
import pypdf

# get datasets index
r = pypdf.PdfReader('canada_forms/templates/imm5257e.pdf')
if r.is_encrypted: r.decrypt('')
xfa = r.root_object.get("/AcroForm").get_object().get("/XFA").get_object()
ds_name = None
for i, item in enumerate(xfa):
    obj = item.get_object() if hasattr(item, "get_object") else item
    try:
        if "datasets" in str(obj):
            ds_name = i + 1
            break
    except:
        pass

shutil.copy('canada_forms/templates/imm5257e.pdf', 'canada_forms/output/test_incremental.pdf')
doc = fitz.open('canada_forms/output/test_incremental.pdf')
# PyMuPDF doesn't need to decrypt if we have owner permissions? Wait, we might need a blank password
if doc.needs_pass:
    doc.authenticate("")

# get XFA
xfa_array = doc.get_acroform().xfa
# xfa_array is a tuple: ((name1, xref1, bytes1), (name2, xref2, bytes2), ...)
ds_xref = None
for name, xref, b in xfa_array:
    if "datasets" == name or b"datasets" in name.encode("utf-8", errors="ignore"):
      ds_xref = xref
      break
    
print(f"datasets xref is {ds_xref}")
if ds_xref:
    # We update the stream
    stream = doc.xref_stream(ds_xref)
    # just a test: replace "1" with "1" to mark it modified
    doc.update_stream(ds_xref, stream)
    doc.saveIncr()
    print("Saved incremental")
