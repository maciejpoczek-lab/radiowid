# Czyta rejestry stacji bazowych UKE (xlsx = zip z XML) bez zewnetrznych bibliotek.
import zipfile, re, glob, os, csv, sys
import xml.etree.ElementTree as ET
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def wiersze(path):
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    arkusz = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    for row in ET.fromstring(z.read(arkusz)).iter("{%s}row" % NS["m"]):
        out = {}
        for c in row.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v = c.find("m:v", NS); t = c.get("t")
            if t == "s" and v is not None: val = ss[int(v.text)]
            elif t == "inlineStr": val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
            else: val = v.text if v is not None else ""
            out[col] = val
        yield out

if __name__ == "__main__":
    for p in sorted(glob.glob(os.path.expanduser("~/dev/showreel-2/dane/uke/*.xlsx")))[:1]:
        for i, w in enumerate(wiersze(p)):
            print(w)
            if i > 3: break
