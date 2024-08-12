import csv
import json
import os
import pickle
import random
from typing import Dict
import numpy as np
import torch
from config import params


def save_metrics_and_params(metrics: Dict[str, float], param_dict: Dict[str, float], filename: str = 'results/model_metrics_and_params_converted.csv') -> None:
    """
    Save metrics and parameters to a JSON file.

    Args:
        metrics (Dict[str, float]): Dictionary of metrics.
        param_dict (Dict[str, float]): Dictionary of parameters.
        filename (str): Filename for the JSON file. Default is 'model_metrics_and_params.json'.
    """
    # Remove certain keys from params
    [param_dict.pop(key, None) for key in ['dataset_path', 'train_path', 'val_path', 'test_path']]

    # Create a dictionary to store both metrics and param_dict
    result = {**metrics, **param_dict}

    file_exists = os.path.isfile(filename)

    # Open the CSV file in append mode
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=result.keys())

        # Write the header only if the file didn't exist before
        if not file_exists:
            writer.writeheader()

        # Write the data
        writer.writerow(result)


def save_epochs(epoch_data, folder_path) -> None:
    if params['additional_features'] and params['study'] == 'feat_engineering':
        filename = params['additional_features'][0] + "_epoch_metrics.csv"
    else:
        filename = "epoch_metrics.csv"
    file = folder_path + filename
    file_exists = os.path.isfile(file)

    # Open the CSV file in append mode
    with open(file, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=epoch_data.keys())

        # Write the header only if the file didn't exist before
        if not file_exists:
            writer.writeheader()

        # Write the data
        writer.writerow(epoch_data)


def set_seeds_and_reproducibility(seed_value, reproducible=True):
    """
    Set seeds for reproducibility and configure PyTorch for deterministic behavior.

    Parameters:
    reproducible (bool): Whether to configure the environment for reproducibility.
    seed_value (int): The base seed value to use for RNGs.
    """
    # Set seeds with different offsets to avoid correlations
    print("Set seeds for reproducibility")
    random.seed(seed_value)
    np.random.seed(seed_value + 1)
    torch.manual_seed(seed_value + 2)
    torch.cuda.manual_seed_all(seed_value + 3)

    if reproducible:
        # Configure PyTorch for deterministic behavior
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    else:
        # Allow PyTorch to optimize for performance
        torch.backends.cudnn.benchmark = True


def convert_to_serializable(val):
    if isinstance(val, (np.int64, np.int32)):
        return int(val)
    elif isinstance(val, (np.float64, np.float32)):
        return float(val)
    elif isinstance(val, list) and len(val) == 1:
        return convert_to_serializable(val[0])
    elif isinstance(val, dict):
        return {k: convert_to_serializable(v) for k, v in val.items()}
    return val


# Function to convert Cartesian to polar coordinates
def cartesian_to_polar(coords):
    polar_coords = []

    if params['3d']:
        for x, y, z in coords:
            r = np.sqrt(x**2 + y**2 + z**2)
            phi = np.arccos(z / r) if r != 0 else 0  # Polar angle from the positive z-axis (colatitude)
            theta = np.arctan2(y, x)  # Azimuthal angle in the xy-plane from the positive x-axis
            polar_coords.append([r, theta, phi])
    else:
        for x, y in coords:
            r = np.sqrt(x ** 2 + y ** 2)  # Radius
            theta = np.arctan2(y, x)  # Angle from the positive x-axis
            polar_coords.append([r, theta])

    # # Convert to numpy array for easier manipulation
    # polar_coords = np.array(polar_coords)
    #
    # # Check range of theta
    # min_theta = np.min(polar_coords[:, 1])
    # max_theta = np.max(polar_coords[:, 1])
    # print(f"Range of theta: [{min_theta}, {max_theta}]")
    #
    # # Check range of radius r
    # min_r = np.min(polar_coords[:, 0])
    # max_r = np.max(polar_coords[:, 0])
    # print(f"Range of radius r: [{min_r}, {max_r}]")
    #
    # quit()

    return polar_coords

