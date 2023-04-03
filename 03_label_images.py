import cv2
import os
import glob
import time
import random
from pathlib import Path
import pandas as pd
from PIL import Image
import numpy as np
import tkinter as tk
from tkinter import ttk
import shutil

def create_backup(database_path):
    folder = os.path.dirname(database_path)
    files = glob.glob(folder + "/*")

    # If a backup already exists, delete it:
    for file in files:
        if "_db_backup_" in file:
            os.remove(file)

    # Create a backup of the database:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    new_backup_path = database_path.replace(".csv", f"_db_backup_{timestamp}.csv")
    shutil.copy(database_path, new_backup_path)
    print("Created a backup of the database at ", new_backup_path)



def create_sorting_window():
    def on_closing():
        sorting_window.quit()

    def on_sort_button_click():
        global selected_option
        selected_option = sorting_var.get()
        on_closing()

    sorting_window = tk.Tk()
    sorting_window.protocol("WM_DELETE_WINDOW", on_closing)
    sorting_window.title("Sort Options")

    sorting_var = tk.StringVar()
    sorting_var.set("uuid")

    radio1 = ttk.Radiobutton(
        sorting_window, text="UUID", variable=sorting_var, value="uuid"
    )
    radio2 = ttk.Radiobutton(
        sorting_window,
        text="Predicted bad first",
        variable=sorting_var,
        value="Predicted bad first",
    )
    radio3 = ttk.Radiobutton(
        sorting_window,
        text="Predicted good first",
        variable=sorting_var,
        value="Predicted good first",
    )
    radio4 = ttk.Radiobutton(
        sorting_window,
        text="middle first",
        variable=sorting_var,
        value="middle",
    )

    sort_button = ttk.Button(sorting_window, text="Sort", command=on_sort_button_click)

    radio1.grid(row=0, column=0, padx=10, pady=10)
    radio2.grid(row=1, column=0, padx=10, pady=10)
    radio3.grid(row=2, column=0, padx=10, pady=10)
    radio4.grid(row=3, column=0, padx=10, pady=10)
    sort_button.grid(row=4, column=0, padx=10, pady=10)

    sorting_window.mainloop()
    return selected_option



def resize(cv_img, size = 1024):
    canvas = Image.new('RGB', (size, size), (0, 0, 0))

    # Resize the image:
    height, width, _ = cv_img.shape
    if height > width:
        ratio = size / height
    else:
        ratio = size / width

    cv_img = cv2.resize(cv_img, (int(width * ratio), int(height * ratio)))

    # paste the image onto the canvas:
    height, width, _ = cv_img.shape
    canvas.paste(Image.fromarray(cv_img), (int((size - width) / 2), int((size - height) / 2)))

    return np.array(canvas)


def relabel_image(uuid, label, database):
    current_timestamp = int(time.time())
    row = database.loc[database["uuid"] == uuid]
    if row is None or len(row) == 0:
        # Create a new entry in the database:
        new_row = {"uuid": uuid, "label": label, "timestamp": current_timestamp}
        database = pd.concat([database, pd.DataFrame([new_row])], ignore_index=True)
    else:
        # Update the existing entry:
        index_to_update = database.loc[database['uuid'] == uuid].index[0]
        # Update the values in the row
        database.loc[index_to_update, 'label'] = label
        database.loc[index_to_update, 'timestamp'] = current_timestamp

    return database



def re_order_images(image_files, database):
    '''
    Takes the pandas dataframe database and sorts the image files according to the "predicted_label" column.
    '''
    sorting_option = create_sorting_window()

    if sorting_option == "uuid":
        image_files = sorted(glob.glob(os.path.join(root_directory, "*.jpg")))

    else:
        # Modify the image_files sorting according to the selected option
        if sorting_option == "Predicted bad first":
            sorted_indices = database['predicted_label'].argsort().values

        elif sorting_option == "Predicted good first":
            sorted_indices = database['predicted_label'].argsort().values[::-1]

        elif sorting_option == "middle":
            # Get the median value of the predicted labels:
            median = database['predicted_label'].median()
            # Get the distance of each predicted label from the median:
            database['distance_from_median'] = abs(database['predicted_label'] - median)
            # Sort the database by the distance from the median:
            sorted_indices = database['distance_from_median'].argsort().values
        
        # get the uuids of those rows in the database:
        uuids = database['uuid'].values[sorted_indices]
        # get the image files that correspond to those uuids:
        image_files = [os.path.join(root_directory, uuid + ".jpg") for uuid in uuids]

    return image_files


def fix_database(database):
    # Loop over all rows of the dataframe
    # When a row has the "label" column filled in, copy that value to the predicted_label column:
    for index, row in database.iterrows():
        label = row['label']
        if (label != "") and (label is not None) and (not np.isnan(label)):
            database.loc[index, 'predicted_label'] = row['label']

    return database


def load_image_and_prompt(uuid, root_directory):
    image_filepath = os.path.join(root_directory, uuid + ".jpg")
    txt_filepath   = os.path.join(root_directory, uuid + ".txt")

    image = cv2.imread(image_filepath)

    if os.path.exists(txt_filepath):
        for line in open(txt_filepath, "r"):
            prompt = line
    else:
        prompt = ''

    return image, prompt

def load(uuid, database):
    # Check if this uuid is already in the database:
    row = database.loc[database["uuid"] == uuid]

    if row is None or len(row) == 0:
        return None
    else:
        return row["label"].values[0]
        
def label_dataset(root_directory, skip_labeled_files = True):
    label_file = os.path.join(os.path.dirname(root_directory), os.path.basename(root_directory) + ".csv")
    image_files = sorted(glob.glob(os.path.join(root_directory, "*.jpg")))

    if os.path.exists(label_file):
        database = pd.read_csv(label_file)
    else:
        database = pd.DataFrame(columns=["uuid", "label", "timestamp"])

    # count how many rows have the label column filled in:
    labeled_count = len(database.loc[database["label"].notnull()])
    print(f"Found {labeled_count} labeled images in {label_file}")

    database = fix_database(database)
    image_files = re_order_images(image_files, database)
    current_index = 0

    while True:
        image_file = image_files[current_index]
        uuid = os.path.basename(image_file).split(".")[0]
        label = load(uuid, database)
        if (label is not None) and (not np.isnan(label)) and skip_labeled_files:
            current_index += 1
            continue

        skip_labeled_files = False

        image, prompt = load_image_and_prompt(uuid, root_directory)
        image = resize(image)
        if label is not None and not np.isnan(label):
            cv2.putText(image, f"{label:.2f} || {prompt}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 100, 25), 2)
        else:
            # Get the predicted label from the database:
            predicted_label = database.loc[database["uuid"] == uuid, "predicted_label"].values[0]
            cv2.putText(image, f"predicted: {predicted_label:.2f} || {prompt}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 100, 25), 2)
            
        cv2.imshow("", image)
        key = cv2.waitKey(0)

        if ord('0') <= key <= ord('9'):
            label = (key - ord('0')) / 10.0
            database = relabel_image(uuid, label, database)
            current_index += 1

            # Save the database:
            database.to_csv(label_file, index=False)

        elif key == ord('q') or key == 27:  # 'q' or 'esc' key
            break
        elif key == 81:  # left arrow key
            current_index -= 1
        elif key == 83:  # right arrow key
            current_index += 1

        current_index = current_index % len(image_files)

        if random.random() < 0.1:
            create_backup(label_file)

    cv2.destroyAllWindows()


"""

cd /home/xander/Projects/cog/CLIP_active_learning_classifier/CLIP_assisted_data_labeling
python 03_label_images.py

"""

if __name__ == "__main__":
    root_directory = "/home/xander/Pictures/datasets/mj_filtered_uuid"
    label_dataset(root_directory)