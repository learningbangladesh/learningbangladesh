import sys, re
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, StreamObject
for fn in sys.argv[1:]:
    r = PdfReader(fn); w = PdfWriter(clone_from=r)
    p = w.pages[0]
    data = p.get_contents().get_data().decode('latin-1')
    data = re.sub(r'BT /F1 [^\n]*?ET', '', data)
    assert 'BT' not in data and 'Tf' not in data
    s = StreamObject(); s.set_data(data.encode('latin-1')); p[NameObject('/Contents')] = w._add_object(s)
    del p['/Resources'][NameObject('/Font')]
    w.add_metadata(r.metadata); w.write(fn)
    r2 = PdfReader(fn); print(fn.split('/')[-1], 'fonts:', r2.pages[0]['/Resources'].get('/Font'), 'BT:', r2.pages[0].get_contents().get_data().count(b'BT'))
