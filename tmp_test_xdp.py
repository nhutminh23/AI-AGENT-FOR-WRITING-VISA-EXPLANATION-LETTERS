import base64
import os

pdf_path = "canada_forms/templates/imm5257e.pdf"
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

b64 = base64.b64encode(pdf_bytes).decode("ascii")

# A dummy <form1> payload that fills the UCI and Name (just to test if it loads data)
dummy_xml = """<form1>
<Page1>
<Header><CRCNum/></Header><Age/><AdultFlag>false</AdultFlag><FormVersion>.ENU-09-2023</FormVersion><PrevSpouseAge/>
<PersonalDetails>
  <UCIClientID>12345678</UCIClientID>
  <Name><FamilyName>TEST</FamilyName><GivenName>USER</GivenName></Name>
</PersonalDetails>
</Page1>
</form1>"""

xdp = f"""<?xml version="1.0" encoding="UTF-8"?>
<?xfa generator="AdobeLiveCycleDesignerES_V10.0.4.20120927.1.870634"?>
<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/" timeStamp="2024-01-01T12:00:00Z" uuid="e05de9d3-e7f3-4d22-ba8f-51d2f63f533a">
  <xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/">
    <xfa:data>
      {dummy_xml}
    </xfa:data>
  </xfa:datasets>
  <pdf xmlns="http://ns.adobe.com/xdp/pdf/">
    <document>
      <chunk>{b64}</chunk>
    </document>
  </pdf>
</xdp:xdp>"""

out_path = "test_standalone.xdp"
with open(out_path, "w", encoding="utf-8") as out:
    out.write(xdp)

print(f"Generated {out_path} ({os.path.getsize(out_path)} bytes)")
