python split_album_pages.py \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04" \
  --output "/Users/dlan/Album Memories 04 PySplit" \
  --debug "/Users/dlan/Album Memories 04 PySplitDebug" \
  --min-area-frac 0.06 \
  --max-area-frac 0.92 \
  --margin 16 \
  --dpi 600



# choose one representative tan page:
python split_album_pages_v2.py tune \
  --image "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --debug "/Users/dlan/Album Memories 04 PySplitDebug/001" \
  --expect 7


python split_album_pages_v2.py run \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04" \
  --output "/Users/dlan/Album Memories 04 PySplit" \
  --debug "/Users/dlan/Album Memories 04 PySplitDebug" \
  --canny-lo 50 --canny-hi 110 --adapt-block 55 --adapt-C 7 --min-area-frac 0.04 \
  --run-n 1


python split_album_corners.py \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --output "/Users/dlan/Album Memories 04 PySplit" \
  --debug "/Users/dlan/Album Memories 04 PySplitDebug" \
  --max-photos 10 


python split_album_corners.py \
  --input "Album Memories 04_001.JPG" \
  --output crops_corners \
  --debug debug_corners \
  --max-photos 12 \
  --min-tri-area 2000 \
  --cluster-tol 140 \
  --margin 12


python sweep_corners.py \
  --image "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --out "/Users/dlan/Album Memories 04 PySplitDebug/001" \
  --expect 7

python sweep_oriented.py \
  --image "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --out "/Users/dlan/Album Memories 04 PySplitDebug/001" \
  --expect 7

python album_split.py sweep \
  --image "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --out "/Users/dlan/Album Memories 04 PySplitDebug/001" \
  --expect 7


python album_split.py run \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --output "/Users/dlan/Album Memories 04 PySplit" \
  --debug "/Users/dlan/Album Memories 04 PySplitDebug" \

  --thr 95 --min-tri-area-frac 1.5e-4 --approx-eps 0.04 \
  --min-area-frac 0.02 --ar-lo 0.65 --ar-hi 2.0 \
  --y-tol-frac 0.02 --x-tol-frac 0.02 \
  --margin 16 --min-expected 4 \
  --dilate-pct-fb 0.035



python album_split.py \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --out "/Users/dlan/Album Memories 04 PySplitDebug/001" \
  --sweep --refine --verbose --stage-dumps \
  --timeout-seconds 0


python box_split_autocorrect.py \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_001.JPG" \
  --out "/Users/dlan/Album Memories 04 PySplitDebug/001" \
  --autocorrect \
  --overlay \
  --margin 6 \
  --min-size-frac 0.08,0.08 \
  --border-frac 0.10 \
  --min-border-ratio 0.40

pip install opencv-python

python box_split_autocorrect.py \
  --input "/Users/dlan/Pictures/Scans/Photo/Album Memories 04/Album Memories 04_003.JPG" \
  --out "/Users/dlan/Album Memories 04 MarkedSplit" \
  --overlay \
  --autocorrect \
  --margin 8 \
  --pure-red

python box_split_autocorrect.py \
  --input "/Users/dlan/Album Memories 04 PySplit/Album Memories 04 marked/Album Memories 04_003.JPG" \
  --out "/Users/dlan/Album Memories 04 MarkedSplit" \
  --pure-red --sweep-red --overlay --dump-mask --target-boxes 4 \
  --rmin 220,235 --gmax 35,25 --bmax 35,25 \
  --smin 120,140 --vmin 120,140 \
  --dilate 5,7 --border-fracs 0.05,0.07 --border-ratios 0.55,0.65 \
  --min-size-frac 0.10,0.10

python box_split_autocorrect.py \
  --input "/path/to/Album Memories 04_003.JPG" \
  --out "/path/to/out" \
  --pure-red --sweep-red --overlay --dump-mask --target-boxes 4 \
  --rmin 220,235 --gmax 35,25 --bmax 35,25 \
  --smin 120,140 --vmin 120,140 \
  --dilate 5,7 --border-fracs 0.05,0.07 --border-ratios 0.55,0.65 \
  --min-size-frac 0.10,0.10

python box_split_ff0000.py \
  --input "/Users/dlan/Album Memories 04 PySplit/Album Memories 04 marked/Album Memories 04_003.JPG" \
  --out "/Users/dlan/Album Memories 04 MarkedSplit" \
  --overlay --dump-mask --autocorrect \
  --margin 2 \
  --edge-thresh 0.2 --max-stroke 80

python album_split_from_marked.py \
  --marked "/path/to/page_marked.jpg" \
  --source "/path/to/page.jpg" \
  --out "/path/to/out" \
  --marker-mode filled --pure-red --overlay --dump-mask \
  --margin 8 --expected 4

python box_split_ff0000.py \
  --input "/Users/dlan/Album Memories 04 PySplit/Album Memories 04 marked/Album Memories 04_003.JPG" \
  --out "/Users/dlan/Album Memories 04 MarkedSplit" \
  --overlay --dump-mask --autocorrect \
  --margin 2 --rmin 220 --gmax 40 --bmax 40 --dilate 5 \
  --edge-thresh 0.05 --max-search 0.20


