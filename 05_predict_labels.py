import os
import numpy as np
import pandas as pd
import torch, shutil
from torch.utils.data import DataLoader, Dataset, random_split
from torch.optim import Adam
import pickle, time
import random
from tqdm import tqdm

from nn_model import device, SimpleFC

"""

cd /home/xander/Projects/cog/CLIP_active_learning_classifier/CLIP_assisted_data_labeling
python 05_predict_labels.py


"""

root_directory = '/home/xander/Pictures/datasets/mj_filtered_uuid'
root_directory = '/data/datasets/midjourney'
model_file = 'models/2023-04-03_13:44:28_1077_10_0.0062.pkl'
batch_size = 16
copy_named_imgs_fraction = 0.01

output_dir = root_directory + '_predicted_scores'
os.makedirs(output_dir, exist_ok=True)


with open(model_file, "rb") as file:
    model = pickle.load(file)

def predict(features, paths, uuids, database, row):
    features = torch.stack(features, dim=0).to(device).float()
    output = model(features)
    output = output.detach().cpu().numpy()

    for i in range(len(output)):
        predicted_score = output[i][0]
        uuid = uuids[i]

        current_timestamp = int(time.time())
        if row is None or len(row) == 0:
            # Create a new entry in the database:
            new_row = {"uuid": uuid, "timestamp": current_timestamp, "predicted_label": predicted_score}
            database = pd.concat([database, pd.DataFrame([new_row])], ignore_index=True)
        else:
            # Update the existing entry:
            index_to_update = database.loc[database['uuid'] == uuid].index[0]
            # Update the values in the row
            database.loc[index_to_update, 'predicted_label'] = predicted_score
            database.loc[index_to_update, 'timestamp'] = current_timestamp

        if random.random() < copy_named_imgs_fraction:

            # Copy the image to the output directory:
            img_path = paths[i]
            outpath = output_dir + f"/{predicted_score:.3f}_{uuid}.jpg"
            shutil.copy(img_path, outpath)

    return database

label_file = os.path.join(os.path.dirname(root_directory), os.path.basename(root_directory) + ".csv")
if os.path.exists(label_file):
    database = pd.read_csv(label_file)
else:
    database = pd.DataFrame(columns=["uuid", "label", "timestamp"])

# add new column 'predicted_label' to the database if not yet present:
if 'predicted_label' not in database.columns:
    database['predicted_label'] = np.nan

# Loop over all *.jpg files in the input_directory that are not yet part of the labeled dataset:
img_files = [f.split('.')[0] for f in os.listdir(root_directory) if f.endswith('.jpg')]
print(f"Predicting labels for {len(img_files)} images...")

features, paths, uuids = [], [], []
n_predictions = 0

for uuid in tqdm(img_files):
    # Get the row in the database that corresponds to this uuid:
    row = database.loc[database["uuid"] == uuid]

    # Check if this uuid is already part of the labeled dataset:
    try:
        if row['label'].values[0] is not None and not np.isnan(row['label'].values[0]):
            continue
    except:
        pass

    img_path = os.path.join(root_directory, uuid + '.jpg')
    feature_path = os.path.join(root_directory, uuid + '.pt')
    feature_vector = torch.load(feature_path).flatten().to(device).float()

    features.append(feature_vector)
    paths.append(img_path)
    uuids.append(uuid)

    if len(paths) == batch_size:
        database = predict(features, paths, uuids, database, row)
        n_predictions += batch_size
        features, paths, uuids = [], [], []
    if n_predictions % 100 == 0:
        database.to_csv(label_file, index=False)

database.to_csv(label_file, index=False)

