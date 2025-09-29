import sys
from pathlib import Path
from PIL import Image

indir = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2] if len(sys.argv)>2 else (indir/"contact_sheet.jpg")).resolve()
imgs = sorted([p for p in indir.glob("*.png") if p.is_file()]) or sorted([p for p in indir.glob("*.jpg") if p.is_file()])

if not imgs:
    raise SystemExit("no images found")

ims = [Image.open(p).convert("RGB") for p in imgs]
w = max(i.width for i in ims)
h = max(i.height for i in ims)
cols = 3
rows = (len(ims)+cols-1)//cols
sheet = Image.new("RGB", (cols*w, rows*h), (30,30,30))

for i, im in enumerate(ims):
    x, y = (i%cols)*w, (i//cols)*h
    sheet.paste(im.resize((w,h), Image.LANCZOS), (x,y))

sheet.save(out)
print(str(out))
