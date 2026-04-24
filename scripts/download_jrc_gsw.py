import os
import urllib.request

DESTINATION_FOLDER = "data/raw/water/jrc_gsw/"
DATASET_NAME = "occurrence"

if not os.path.exists(DESTINATION_FOLDER):
    os.makedirs(DESTINATION_FOLDER)

# Africa only — roughly 20W to 60E, 40S to 40N
longs = [str(w) + "W" for w in range(20, 0, -10)]
longs.extend([str(e) + "E" for e in range(0, 60, 10)])
lats = [str(s) + "S" for s in range(40, 0, -10)]
lats.extend([str(n) + "N" for n in range(0, 40, 10)])

for lng in longs:
    for lat in lats:
        filename = f"{DATASET_NAME}_{lng}_{lat}v1_4_2021.tif"
        filepath = DESTINATION_FOLDER + filename
        if os.path.exists(filepath):
            print(f"Already exists - skipping {filename}")
            continue
        url = f"http://storage.googleapis.com/global-surface-water/downloads2021/{DATASET_NAME}/{filename}"
        try:
            code = urllib.request.urlopen(url).getcode()
            if code != 404:
                print(f"Downloading {filename}")
                urllib.request.urlretrieve(url, filepath)
            else:
                print(f"Not found: {filename}")
        except Exception as e:
            print(f"Error downloading {filename}: {e}")